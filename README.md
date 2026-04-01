# lime_counter
Counting limes in production

## Showcase workflow

### 1) Draw counting line on first frame

```bash
python line_selector_app.py --source example_media/lime_1.mp4 --output output/count_line.json
```

- Draw a line with the mouse.
- Press `s` to save, `r` to reset, `q` to quit.

### 2) Run showcase counter app

```bash
python showcase_counter_app.py --source example_media/lime_1.mp4 --line-config output/count_line.json --show --save --output output/showcase_counted.mp4 --cooldown-frames 12 --stats-output output/showcase_stats.json
```

The app uses tracking + supervision line trigger and overlays:
- counting line
- IN / OUT counts
- total count

It also includes:
- debounce/smoothing for repeated line crossings per tracker (`--cooldown-frames`)
- run statistics export to JSON (`--stats-output`)
