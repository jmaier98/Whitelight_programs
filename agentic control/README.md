# White-light microscope: agentic control

The same layout as `HRRWLPP/Master program v2 (AGENTIC)` (tabs, a controller, an agent
panel, a context file), built for the white-light microscope's own hardware. It
covers what `TwoDscan.py`, `arduino_control_v2.py` and `Gate_testing_breakdown.py` did.

Run it with:

```
python main.py
```

## Layout

| File / folder | What it is |
|---|---|
| `main.py` | Main window: tabs on top, agent panel (task box, chat, full log) below |
| `controller.py` | One API for the tabs and the agent: stage moves with alignment offsets, ps→mm delay, gate ramps that watch both gates, every scan axis and measurement |
| `microscope_state.py` | The state variable. Every driver writes what it just set into it. It is saved to `microscope_state.json` and copied into the header of every data file |
| `instrument_manager.py` | Opens each instrument. **The `INSTRUMENTS` table at the top holds every port/address**; edit it when the setup changes, or set an entry to `False` to skip hardware that is not installed |
| `agent_tools.py`, `agent_worker.py` | Tools the agent can call, and the Ollama loop (server address at the top of `agent_worker.py`) |
| `context.txt` | Operator norms the agent reads, one `[Section]` per tab (editable in the Context / Norms tab) |
| `drivers/` | ESP301 (COM7), BTT rotation mounts (COM4), SP2500 (COM5), MLJ050 Z stage (COM8), Arduino (COM3), three SR830 lock-ins (GPIB 8, 7, 26), SR400 photon counter (GPIB 23), Keithley top gate (GPIB 24) and back gate (GPIB 22) |
| `tabs/` | Instrument Controls, 2D Scan, Alignment, Gate Breakdown, Arduino |
| `helpers/` | Electrode fitter (copied from `v2 controls`) and the state header writer |
| `procedures/` | PDFs of standard procedures the agent can follow (needs `pip install pymupdf`) |

## Differences from the old programs

- **Saved 2D data** keeps the old column order (`Scan_Number Y X data…`, all header lines
  start with `#`), so `datavisualizerv2.py` still reads it. There are now 9 data columns
  (the 4-channel dichroism needs 9), unmeasured points are `nan` instead of `0`, and the
  header also lists the full instrument state.
- **Gate breakdown sweep** now really ramps the gate back to 0 V. The old code only wrote the
  first point of the ramp, which left the gate biased.
- **Y pos retry**: the old 2D scan retried a failed Y move by moving X. That is fixed.
- **Keithleys** stay connected instead of reconnecting on every command, and their output is
  not switched on or reset when the program starts.
- **Not carried over**: the `Delay time (ps)_yaxis` axes (they drove ESP axis 2, the sample Y
  stage, as a delay line), the unused polarisation sweep, and the old `Reverse delay time`
  axis. Its formula was the same as `Delay time (ps)` but it waited for the stage; that is
  now `Delay time (ps), wait for stage`.
- **Camera** opens with DirectShow (`cv2.CAP_DSHOW`), like the new microscope's webcam tab,
  instead of OpenCV's slow Windows default. It starts off; press "Turn camera on" in the
  Arduino tab.

## Startup with missing instruments

Every instrument has to answer a short query (`*IDN?`, the ESP301 `VE?`, the SP2500 `?NM`,
the SR400 `QA`) before it counts as present, because a GPIB address or COM port can open
with nothing behind it. Each lock-in is checked on its own. Missing instruments are listed:

- in the console, as a table with the reason and how long each check took
- in the window's status bar (orange if anything is missing; hover for the table)
- in the agent's full log, and in `get_state`, so the agent knows too

Their controls are greyed out, and axes and measurements that need them are not offered
(for example, without lock-in 3, "Lockin 3" and "Photocurrent and R" disappear).

The Z stage homes itself at startup if it is not already homed, which can take up to a
minute; the old TwoDscan did the same.
