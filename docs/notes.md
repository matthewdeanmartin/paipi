## Notes

- hallucinates packages that don't exist, but something with a similar name does (sonarque's python package)
- could ground further in post searching (bot imagines, then throws out hallucinations)
- could ground in presearch  (bot searches and decides if things it found are relevant, repeat until finds the thing)
- could ground in search where the bot is coming up with queries/advanced queries

## TODO

- preflight check to see if README.md already exists
- maybe look up actual library if it already exists & swap out real data
- generate a list (small number of tokens), then generate the json for the hallucinated ones (use real results for real ones)
- more button (list already seen so they're not re-imagined)