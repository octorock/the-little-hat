# <img src="resources/icon.png" width=64 /> The Little Hat

_The Little Hat_ is a glorified hex diff viewer that improves the diff over time using the _constraints_ between the different files that were found. It is specifically built to help find pointers for the tmc decomp and is still in an early stage where everything might crash every second.

## Setup
```bash
git clone git@github.com:octorock/the-little-hat
cd the-little-hat
make
```

### Run
```bash
cd the-little-hat
make run
```

### Run tests
```bash
cd the-little-hat
make test
```

[First Steps](docs/first_steps.md)

[Using the CExplore Bridge plugin](docs/cexplore_bridge.md)

## Advanced
[Create Plugin](docs/create_plugin.md)