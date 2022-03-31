#!/usr/bin/env python

# Tool cpp-header-checker
#
# Copyright (C) 2022 Wang Qi (wqking)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import sys
import os
import glob
import argparse
import traceback
import threading
import queue
import tempfile
import random
import string
import time
import shutil
import codecs
import re
import pathlib

def getRandomString(length) :
	return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def writeFile(fileName, content) :
	with codecs.open(fileName, "w", "utf-8") as file :
		file.write(str(content))

def readFile(fileName) :
	with codecs.open(fileName, "r", "utf-8") as file :
		return file.read()

def removeNthInclude(content, n) :
	success = False
	include = ''
	def callback(m) :
		nonlocal n, success, include
		n -= 1
		if n == -1 :
			success = True
			include = m.group(1)
			return ''
		else :
			return m.group()
	result = re.sub(r'(^\s*\#\s*include.*$)', callback, content, flags = re.M)
	return result, success, include

def test_removeNthInclude() :
	content = '''aaa
	#include "abc.h"
	bbb
	#include <xyz/def.h>
	ccc
	'''
	print(removeNthInclude(content, 0))
	print(removeNthInclude(content, 1))
	print(removeNthInclude(content, 2))

class TaskProcessor :
	def __init__(self, app) :
		self._app = app
		self._tempPath = None

	def initialize(self) :
		self._tempPath = os.path.join(self._app.getTempPath(), self.getRandomFileName())
		os.mkdir(self._tempPath)

	def finalize(self) :
		shutil.rmtree(self._tempPath)

	def getApp(self) :
		return self._app

	def makeTempFileName(self, fileName) :
		return os.path.join(self._tempPath, fileName)

	def makeCommand(self, sourceFile) :
		command = self._app.getCommand()
		command = command.replace('{file}', sourceFile)
		return command

	def makeMainSourceCode(self, header) :
		code = ''
		code += '#include "%s"\n' % (header)
		return code

	def getRandomFileName(self, ext = None) :
		fileName = '%s_%s_%s' % (
			getRandomString(12),
			str(threading.get_ident()),
			str(int(time.time()))
		)
		if ext is not None :
			fileName += ext
		return fileName

	def process(self, headerFile) :
		header = os.path.abspath(headerFile)
		self.doProcess(header)

	def doProcess(self) :
		pass

class CompleteHeaderProcessor(TaskProcessor) :
	def __init__(self, app):
		super().__init__(app)

	def doProcess(self, header) :
		mainFileName = self.getRandomFileName('.cpp')
		fullMainFileName = self.makeTempFileName(mainFileName)
		command = self.makeCommand(fullMainFileName)
		writeFile(fullMainFileName, self.makeMainSourceCode(header))
		result = subprocess.run(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines = True)
		if result.returncode == 0 :
			self.getApp().log('%s - OK' % (header))
		else :
			self.getApp().log('%s - ERROR\n%s' % (header, result.stdout))

class RedundantHeaderProcessor(TaskProcessor) :
	def __init__(self, app):
		super().__init__(app)

	def doProcess(self, header) :
		headerContent = readFile(header)
		includeIndexToRemove = 0
		redundantIncludeList = []
		while not self.getApp().shouldStop() :
			content, success, include = removeNthInclude(headerContent, includeIndexToRemove)
			if not success :
				break
			includeIndexToRemove += 1
			newHeaderName = self.getRandomFileName('.h')
			newFullHeaderName = os.path.join(pathlib.Path(header).parent.resolve(), newHeaderName)
			writeFile(newFullHeaderName, content)
			try :
				mainFileName = self.getRandomFileName('.cpp')
				fullMainFileName = self.makeTempFileName(mainFileName)
				command = self.makeCommand(fullMainFileName)
				writeFile(fullMainFileName, self.makeMainSourceCode(newFullHeaderName))
				result = subprocess.run(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines = True)
				if result.returncode == 0 :
					include = include.replace('#include', '')
					include = re.sub(r'[\"\'\<\>]', '', include)
					include = include.strip()
					redundantIncludeList.append(include)
			finally:
				os.unlink(newFullHeaderName)

		if len(redundantIncludeList) == 0 :
			self.getApp().log('%s - OK' % (header))
		else :
			# Display log after all #includes are checked, this ease for looking at the errors
			self.getApp().log('%s - ERROR redundant: %s' % (header, ', '.join(redundantIncludeList)))

class Application :
	def __init__(self) :
		self._sourcePatternList = []
		self._excludePatterns = []
		self._command = 'gcc {file} -c -o {file}.o'
		self._tempPath = None
		self._threads = None
		self._queue = queue.Queue()
		self._lock = threading.Lock()
		self._processor = None
		self._stopping = False

	def getCommand(self) :
		return self._command

	def getTempPath(self) :
		return self._tempPath

	def log(self, message) :
		with self._lock :
			print(message)

	def error(self) :
		self._stopping = True

	def shouldStop(self) :
		return self._stopping

	def run(self) :
		if not self._parseCommandLine(sys.argv[1:]) :
			return
		self._processor.initialize()
		try :
			self._doRun()
		except Exception as e:
			traceback.print_exc()
		finally :
			self._processor.finalize()

	def _doRun(self) :
		for pattern in self._sourcePatternList :
			fileList = glob.glob(pattern, recursive = True)
			for file in fileList :
				if self._canProcessFile(file) :
					self._queue.put(file)
		threadList = []
		for i in range(self._threads) :
			thread = threading.Thread(target = lambda : self._executeThread())
			threadList.append(thread)
			thread.start()
		for thread in threadList :
			thread.join()

	def _executeThread(self) :
		while not self.shouldStop() :
			try :
				task = self._queue.get(block = False)
			except :
				task = None
			if task is None :
				break
			self._doTask(task)
			self._queue.task_done()

	def _doTask(self, task) :
		self._processor.process(task)

	def _canProcessFile(self, file) :
		for exclude in self._excludePatterns :
			if exclude in file :
				return False
		return True

	def _parseCommandLine(self, commandLineArguments) :
		parser = argparse.ArgumentParser(add_help = False)
		parser.add_argument('--help', action = 'store_true', help = 'Show help message')
		parser.add_argument('-h', action = 'store_true', dest = 'help', help = 'Show help message')
		parser.add_argument('--source', action = 'append', required = True, help = "The source file patterns, can have path and wildcard")
		parser.add_argument(
			'action',
			nargs='?',
			help = "The action, can be complete or redundant",
			default = 'complete',
			choices = [ 'complete', 'redundant' ]
		)
		parser.add_argument('--command', required = False, help = "Command", default = self._command)
		parser.add_argument('--temp', required = False, help = "Temp path", default = None)
		parser.add_argument('--exclude', action = 'append', required = False, help = "The patterns to exclude, can not have wildcard")
		parser.add_argument('--threads', required = False, type = int, help = "Number of threads", default = None)

		if len(commandLineArguments) == 0 :
			self._showUsage(parser)
			return False

		try :
			options = parser.parse_args(commandLineArguments)
			options = vars(options)
		except :
			self._showUsage(parser)
			return False

		if options['help'] :
			self._showUsage(parser)
			return False

		self._sourcePatternList = options['source']
		self._command = options['command']
		self._tempPath = options['temp']
		if self._tempPath is None :
			self._tempPath = tempfile.gettempdir()
		self._tempPath = os.path.join(self._tempPath, '') # append /
		self._excludePatterns = options['exclude']
		if self._excludePatterns is None :
			self._excludePatterns = []
		self._threads = options['threads']
		if self._threads is None :
			self._threads = os.cpu_count()
		if self._threads is None or self._threads < 1 :
			self._threads = 1
		action = options['action']
		if action == 'redundant' :
			self._processor = RedundantHeaderProcessor(self)
		else :
			self._processor = CompleteHeaderProcessor(self)
		return True

	def _showUsage(self, parser) :
		parser.print_help()

Application().run()
