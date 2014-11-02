# SuperCollider Sublime Text 3 Plugin

Rewritten for Sublime Text 3 based on ST2 plugin by[geoffroymontel](https://github.com/geoffroymontel/supercollider-package-for-sublime-text).

Also includes:
- SCLang Syntax by [rfwatson](https://github.com/rfwatson/supercollider-tmbundle)
- SCHelp Syntax by [crucialfelix](https://github.com/crucialfelix)

## Known Issues

### Single SCLang instance

This plugin currently only supports a single instance of SCLang.
To run multiple instances would require:

- Rewriting SuperColliderProcess to create instances
- Different names for each temp file

### Empty Post window

Occasionally when re-opening the post window, or whenever re-opening in a different window/tab, cached content isn't retrieved...

## TODO

### SuperCollider.py

- if post window moved to another pane/window, can't restore
- if re-open last tab and context SC, then open new post window
- option on where to open post window: new tab, new group, new window,terminal
- refocus on original window on open_post_view
- re-write with plugin_loaded and process instance?
- default keymaps for other OSs
- command: stop sclang key binding
- command: recompile class library
- command: show server meter
- command: dump node terminated
- command: dump node tree with controls
- command: evaluate file
- command: Stop
- command: rename start/stop StartSCLang etc
- command: look up implementations for selection
- command: look up references
- command: reboot
- command: open user support dir
- command: open startup file
- option: boot interpreter on set syntax

### Auto complete

- Make easy to do ctags
- Include default symbol list from core

### Key map

- Windows
- Linux
- OS X

### Menu

### Include schelp syntax by CrucialFelix, in Geoffroy Montel repo