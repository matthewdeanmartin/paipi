## Observations

- some models hallucinate fun packages, some models stick to packages that they know exist for sure
- For some models the Readme.md is really lame

## Package Generation

- The bot often forgets to write anything to a file! So many empty files!
- Maybe seed it with a half decent build script?

## Improving Creativity 

- hallucinates packages that don't exist, but something with a similar name does (sonarque's python package)
- Rotate bots for hallucinating (some hallucinate packages more than others)

## Improving reality

- could ground further in post searching (bot imagines, then throws out hallucinations)
- could ground in presearch  (bot searches and decides if things it found are relevant, repeat until finds the thing)
- could ground in search where the bot is coming up with queries/advanced queries

## TODO

- more button (list already seen so they're not re-imagined)
- move paipi_cache.db into pypi_cache folder. (bad name!)
- better support for rst
- make markdown less ugly (open in new tab?)
