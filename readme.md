# cpp-header-checker -- tool for checking C++ header integration and redundance

cpp-header-checker is a tool that can check C++ source file that  
1. If a C++ header file is self contained. If a header is self contained, it can be included without any other header files.  
2. If a C++ file has redundant `#include`. Redundant `#include` means if the include is removed, the file can be compiled without errors.  
 
The tool is written in Python 3, tested with Python 3.8.10.  

## Features

- Check if header files are self contained.
- Check if any `#include` is redundant and can be removed.
- Utilize multi-threading. The check is pretty fast.
- Not intrusive. The tool doesn't modify the source files.
- Support checking multiple files.
- Support checking files recursively in nested folders.

## License

Apache License, Version 2.0  

## Source code

[https://github.com/wqking/cpp-header-checker](https://github.com/wqking/cpp-header-checker)

## Command line

```
python cpp-header-checker.py ACTION [--help] [-h] --source SOURCE [--command COMMAND] [--temp TEMP] [--exclude EXCLUDE] [--threads THREADS]
```

#### ACTION, optional

The action can be `complete` or `redundant`. Default is `complete`.  
If the action is `complete`, it will check if the header files are self contained.  
If the action is `redundant`, it will check for redundant.  

#### --source SOURCE, required

SOURCE is the file pattern of the source files, the pattern can include wildcard `*`, and may include `**` to indicate recursive folders.  
There can be multiple `--source SOURCE`.  
The source can be C++ header files, or C++ source files.  
Note: on Linux shell, the recursive wildcard `**` maybe expanded to multiple files by the shell, that will cause wrong arguments to the tool. To fix that, escape the second *, that's `*\*`. For example, `--source ~/projects/eventpp/include/*\*/*.h`. On Windows the second * doesn't need the escape.

#### --command COMMAND, optional, but usually you should specify it

The compile command to compile the file to do the check.  
The default is `gcc {file} -c -o {file}.o`.  
The tag `{file}` is replaced with the C++ source file name.  
Any command can be specified, the only requirement is that the command must exit with code 0 for success, other exit code for fail.  
Usually you should set the command to use a C++ compiler to compile the `{file}`, but not link it (see `-c` in the default command), and you may need to set proper include directory to your project.  
Any C++ compiler can be used, not limit to GCC.  
See "How it works" section for details.

#### --temp TEMP, optional

Specify the directory to store the temporary files.  
The default is system temporary directory.  
The folder TEMP must exist when running the tool.  
After the tool finishes, all temporary files are deleted.  

#### --exclude EXCLUDE, optional

Specify the file names to be excluded from the source files.  
`EXCLUDE` can't contain any wildcard. The tool checks if any source file name or path contains `EXCLUDE`, then the tool skips that file.  
There can be multiple `--exclude EXCLUDE`.  

#### --threads THREADS, optional

Specify the number of threads to execute the check. Default is the number of CPU cores.  

## Examples

#### Check self contained headers for eventpp library

Below command can check if the headers are self contained in my [eventpp library](https://github.com/wqking/eventpp)

```
python cpp-header-checker.py complete --source EVENTPP_FOLDER/include/**/*.h --temp ./temp --command "gcc {file} -c -o {file}.o -IEVENTPP_FOLDER/include" --exclude _i.h
```

#### Check redundant #include for eventpp library

Below command can check if any `#include` is redundant in my [eventpp library](https://github.com/wqking/eventpp)

```
python cpp-header-checker.py redundant --source EVENTPP_FOLDER/include/**/*.h --temp ./temp --command "gcc {file} -c -o {file}.o -IEVENTPP_FOLDER/include" --exclude _i.h
```

## How it works

The tool creates a C++ source file with a unique random name in a sub-directory under the folder specified by `--temp`, then uses the command specified by `--command` to compile the source file. For different actions, the tool uses different strategies to do the check.

For action `complete`, which checks for self contained headers, the tool puts `#include` of the header being checked in the source file directly. Then the tool compiles the source file. If the compilation succeeds with exit code 0, the tool considers the header to be self contained. If the compiling fails with non-zero exit code, the tool considers the header to be not self contained, it reports an error and print the compiler error messages. Then the programmer can fix the compiler errors until the tool doesn't report an error.  

For action `redundant`, which checks if any `#include` is redundant, the tool will create a temporary file in the directory where the header file is in. The temporary file contains all code of the header, except that one `#include` is removed. Then the tool `#include` that temporary header in a C++ source file, then the tool compiles it. If the compiling fails with non-zero exit code, the tool treats it as success. If the compiling succeeds with exit code 0, the tool reports error that the removed `#include` is redundant. To fix a redundant `#include`, the programmer should remove them manually then build the C++ project to see if it still compiles. Don't rely on the tool because it can give false results.  

## Note when checking redundant  
1. Before checking for redundant, the source files must be self-contained. That's to say, you should use `complete` action and be sure the tool doesn't find any errors.  
2. The folder where the C++ files are in must be writable by the tool, because the tool will create temporary C++ files there, but the tool won't modify any existing C++ files.  
3. The tool may give false results, especially when the C++ file has lots of templates. A template may be compiled successfully on the first phase, but fail on the second phase, the tool only checks for first phase. Note checking for self contained (complete) usually doesn't give a false result.   
4. If the tool reports #include A and #include B are redundant, it's possible that only one of A or B is redundant, not both. For example, if B includes A, then A is redundant, but B is not.  
5. If B includes A, and a file includes both A and B, and the file uses features in A directly. Though A will be reported as redundant, you'd better keep A in the file because the file uses it. Though it doesn't harm to remove A from the includes. This point is my personal opinion.  

## Final words
Please use this tool as an auxiliary, not an ultimate tool. You need to check the result carefully and decide how to modify the source files.  
Though the tool won't modify any source files, you'd better backup or commit your files before running the tool.  
I've used this tool in my [eventpp library](https://github.com/wqking/eventpp) and fixed several header related problems.  
