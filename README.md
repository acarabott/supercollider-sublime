# SuperCollider Sublime Text 3 Plugin

Rewritten for Sublime Text 3 based on ST2 plugin by [geoffroymontel](https://github.com/geoffroymontel/supercollider-package-for-sublime-text).

Also includes:
- sclang Syntax by [rfwatson](https://github.com/rfwatson/supercollider-tmbundle)
- schelp Syntax by [crucialfelix](https://github.com/crucialfelix)

## Features

- Execute with multiple cursors
- Execution highlighting
- Search Help directly from Sublime Text
- Post window can open in a new tab, group, window, or output panel (see settings file)
- Optional max length for post window
- Post window scrolls if at the bottom, doesn't if user scrolls up
- Fancy block evaluation, expands to lines containing brackets, e.g. executing with the cursor inside a SynthDef will evaluate it without containing parentheses.
- Near parity with SCIDE commands, e.g. Open User Support Directory, and Open Startup File

See SuperCollider.sublime-settings for options

All commands are available in the Tools > SuperCollider Menu

## Testing TODO

- Windows
    - Communication with sclang
    - 'Open Startup File' command
    - 'Open User Support Directory' command
- Linux
    - 'Open Startup File' command
    - 'Open User Support Directory' command

## TODO

### Release
- SuperCollider.sublime-commands file
- Menu: add all commands
- Add snippets
- decide on best keymaps
- add user keymap
- default keymaps for other OSs

### Future
- command: show node tree
- command: dump node terminated
- command: dump node tree with controls
- command: look up references
- Include schelp syntax by CrucialFelix, in Geoffroy Montel repo
- autocomplete
    - Make easy to do ctags
    - Include default symbol list from core
- mini html for error logs with felix' parsing

## Future Work

### Multiple sclang instances

In theory this plugin could support multiple instances of sclang, however some mechanism would be required to tell the commands (start, stop execute etc) which instance to send the message to.

#### Possibile approaches:

- Selectable 'current sclang' menu item
