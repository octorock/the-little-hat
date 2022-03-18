# Asm Differ
Cherry pick this commit: https://github.com/octorock/tmc/commit/242f687e5df8347eb795123e84f85b2002445eb5

Run `python diff.py`
Use the provided command to install the dependencies using pip

```python3 diff.py -o sub_08085F48 -w -m```

Create the expected .o file
```
mkdir -p expected/build/tmc/src/object
cp build/tmc/src/object/lilypadLarge.o expected/build/tmc/src/object/
```

Add `#define NON_MATCHING 1` to the beginning of `global.h`
TODO agbcc does not support defining via arguments like -DNONMATCHING=1?

```
rm build/tmc/src/object/lilypadLarge.o
python3 diff.py -o sub_08085F48 -w -m
```