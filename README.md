# SuperCollider Sublime Text 3 Plugin

## Installation

- Either clone this repo into your Sublime Text 3/Packages folder, or install via Package Control
- Set the path for the sclang executable: go to Preferences > Package Settings > SuperCollider > Settings - User
- Add the following settings, modifiying the `sc_dir` to match the location of SuperCollider on your machine. e.g. 

### OS X
To verify the correct path, ctrl click on the SuperCollider applicationa and choose 'Show Package Contents'
```
{
    "sc_dir": "/Applications/SuperCollider/SuperCollider.app/Contents/MacOS/"
}
```

### Windows
```
{
    "sc_dir": "C:\\Programs\\SuperCollider\\SuperCollider\\"
}
```

## Features

- Execute with multiple cursors
- Execution highlighting
- Open Help and Class files directly from Sublime Text
- Post window in a new tab, group, window, or output panel (see settings file)
- Fancy block evaluation, expands to lines containing brackets, e.g. executing with the cursor inside a SynthDef will evaluate it without the need for additional parentheses.
- Near parity with SCIDE commands, e.g. Open User Support Directory, and Open Startup File

## Options

See `Preferences > Package Settings > SuperCollider > Settings - Default` for further options, including Post Window settings.

## Commands

All commands are available in the Tools > SuperCollider Menu, or via the Command Palette

## Credits

Rewritten for Sublime Text 3 based on ST2 plugin by [geoffroymontel](https://github.com/geoffroymontel/supercollider-package-for-sublime-text).

Also includes:
- sclang Syntax by [rfwatson](https://github.com/rfwatson/supercollider-tmbundle)
- Some snippets and mouse mapping from Thor Magnusson

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
- Check Windows path example

- Use new .sublime-syntax format
- Use system dialog to select SuperCollider application location
- Provide syntax error feedback in open document (e.g. highlight line with errors)
- command: show node tree
- command: dump node terminated
- command: dump node tree with controls
- command: look up references
- autocompletion
    - Make easy to do ctags
    - Include default symbol list from core
- add schelp syntax from [crucialfelix](https://github.com/crucialfelix)'s Atom plugin
- mini html for error logs with crucialfelix's parsing
    + probably use supercollider.js for this

## Future Work

### Multiple sclang instances

In theory this plugin could support multiple instances of sclang, however some
mechanism would be required to tell the commands (start, stop execute etc) which
instance to send the message to.

#### Possibile approaches:

- Selectable 'current sclang' menu item
