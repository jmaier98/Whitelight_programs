"""
Agent tool definitions for the white-light microscope.

dispatch() returns either
  - dict  → plain JSON result
  - list  → multipart content [image blocks…, text block] (scans, camera, procedures)
"""
import json

import procedure_loader
from controller import MicroscopeController

_EMPTY = {"type": "object", "properties": {}, "required": []}


def _tool(name, description, properties=None, required=None):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties or {},
                             "required": required or []}}


TOOLS = [
    _tool("list_procedures",
          "List the saved measurement procedures (PDFs). Call this when the user asks to run "
          "or follow a named procedure or standard setup."),
    _tool("get_procedure",
          "Load a procedure by name: its written steps as text plus an image of every page "
          "(including reference images of good/bad results). Then carry out the steps in order.",
          {"name": {"type": "string", "description": "Procedure name from list_procedures"}},
          ["name"]),

    _tool("get_state",
          "Current microscope state: connected instruments, instruments that failed to open, "
          "and every setting (stage X/Y in µm, alignment offsets, delay in ps and mm, Z, "
          "wavelength, rotation mounts, gate voltages, photon-counter settings, Arduino states)."),
    _tool("list_instrument_controls",
          "List every single-value control in the Instrument Controls tab (e.g. 'X pos (µm)', "
          "'Delay (ps)', 'Top gate (V)', 'Waveplate angle (°)') with its current value."),
    _tool("list_instrument_buttons",
          "List the command buttons in the Instrument Controls tab (e.g. 'Reset alignment "
          "offsets', 'Ramp both gates to 0 V')."),
    _tool("set_instrument_control",
          "Set one control to a value and wait until it is there (like typing a value and "
          "pressing Go). Gate voltages are always ramped and abort (ramping BOTH gates to 0 V) "
          "if either gate leaks more than the gate current limit.",
          {"control": {"type": "string", "description": "Control label (case-insensitive)"},
           "value": {"type": "number"}},
          ["control", "value"]),
    _tool("press_instrument_button", "Press a command button in the Instrument Controls tab.",
          {"button": {"type": "string", "description": "Button label (case-insensitive)"}},
          ["button"]),

    _tool("get_2d_scan_settings",
          "Return every 2D Scan tab setting plus the available axis names, measurement names "
          "and the data channels (data1…data9) the selected measurement produces. Call this "
          "before configuring a scan."),
    _tool("set_2d_scan_settings",
          "Configure any subset of the 2D Scan tab. X is the fast axis, Y the slow axis. "
          "Ranges are start/end/step; or set custom_x/custom_y with comma-separated values. "
          "For 'Gate line cut (TG, BG)' the axis values are the top gate and the back gate "
          "runs from line_cut_bg_start to line_cut_bg_end over the same points. "
          "wait_s is the wait per point in SECONDS. All fields optional.",
          {"x_axis": {"type": "string"}, "y_axis": {"type": "string"},
           "measurement": {"type": "string"},
           "x_start": {"type": "number"}, "x_end": {"type": "number"}, "x_step": {"type": "number"},
           "y_start": {"type": "number"}, "y_end": {"type": "number"}, "y_step": {"type": "number"},
           "averages": {"type": "integer", "description": "Number of full scans to average"},
           "wait_s": {"type": "number", "description": "Wait per point (s)"},
           "custom_x": {"type": "boolean"}, "custom_x_values": {"type": "string"},
           "custom_x_backgate_values": {"type": "string"},
           "custom_y": {"type": "boolean"}, "custom_y_values": {"type": "string"},
           "custom_y_backgate_values": {"type": "string"},
           "line_cut_bg_start": {"type": "number"}, "line_cut_bg_end": {"type": "number"},
           "align_before_each_scan": {"type": "boolean"},
           "align_every_n_rows": {"type": "boolean"}, "align_n": {"type": "integer"},
           "image_1_channel": {"type": "string", "description": "'data1'…'data9'"},
           "image_2_channel": {"type": "string", "description": "'data1'…'data9'"},
           "show_average": {"type": "boolean"},
           "device": {"type": "string"}, "pump_power": {"type": "string"},
           "pump_wavelength": {"type": "string"}, "probe_power": {"type": "string"},
           "probe_wavelength": {"type": "string"}, "notes": {"type": "string"},
           "folder": {"type": "string"}, "filename": {"type": "string"},
           "autosave": {"type": "boolean"}, "save_picture": {"type": "boolean"}}),
    _tool("run_2d_scan",
          "Run the 2D scan with the current 2D Scan tab settings and wait for it to finish. "
          "Returns a picture of the plots plus min/max/mean of every data channel. If autosave "
          "is on the data is saved automatically."),
    _tool("save_2d_scan",
          "Save the most recent 2D scan (.txt with full header incl. instrument state, plus "
          ".png). Never overwrites — a numeric suffix is added if needed.",
          {"filename": {"type": "string", "description": "Optional base filename (no extension)"}}),

    _tool("get_alignment_settings",
          "Return the Alignment tab settings: cut start position, directions, distances, fit "
          "model, target position, and the current origin and X/Y offsets."),
    _tool("set_alignment_settings", "Configure any subset of the Alignment tab settings.",
          {"x_init_um": {"type": "number"}, "y_init_um": {"type": "number"},
           "x_direction": {"type": "string", "description": "'right' or 'left'"},
           "y_direction": {"type": "string", "description": "'down' or 'up'"},
           "x_distance_um": {"type": "number"}, "y_distance_um": {"type": "number"},
           "fit_model": {"type": "string",
                         "description": "'double sigmoid (hat)' or 'single sigmoid (step)'"},
           "hat_width_um": {"type": "number"}, "settle_s": {"type": "number"},
           "move_to_target": {"type": "boolean"},
           "x_target_um": {"type": "number"}, "y_target_um": {"type": "number"}}),
    _tool("run_alignment",
          "Sweep across the feature in X and Y with lock-in 1, fit each cut, and either set "
          "the reference origin (set_origin=true) or measure the drift from it and store it as "
          "the X/Y offset applied to every later stage move.",
          {"set_origin": {"type": "boolean", "default": False}}),

    _tool("get_gate_settings",
          "Return the Gate Breakdown tab settings and both gates' present voltage and output "
          "state, compliance, the sweep parameters and the last breakdown voltage."),
    _tool("set_gate_settings",
          "Configure any subset of the Gate Breakdown tab. Compliance values are sent to the "
          "Keithleys immediately. All fields optional.",
          {"sweep_gate": {"type": "string", "description": "'top' or 'back'"},
           "v_start": {"type": "number"}, "v_end": {"type": "number"},
           "v_step": {"type": "number"}, "dwell_ms": {"type": "integer"},
           "abort_current_a": {"type": "number",
                               "description": "Stop when |I| of EITHER gate reaches this (A)"},
           "ramp_down_v_per_s": {"type": "number"},
           "top_compliance_a": {"type": "number"}, "back_compliance_a": {"type": "number"},
           "log_scale": {"type": "boolean"},
           "folder": {"type": "string"}, "filename": {"type": "string"}}),
    _tool("set_gate_voltage",
          "Ramp the top or back gate to a voltage and wait until it is there (never jumps).",
          {"gate": {"type": "string", "description": "'top' or 'back'"},
           "volts": {"type": "number"}},
          ["gate", "volts"]),
    _tool("run_gate_sweep",
          "Run a breakdown sweep with the current Gate Breakdown settings and wait. Stops when "
          "either gate's |I| reaches the abort current or the source hits compliance, then "
          "ALWAYS ramps the swept gate back to 0 V. Returns an I-V plot and the breakdown "
          "voltage (null if none)."),
    _tool("save_gate_sweep", "Save the most recent gate sweep (.txt + .png).",
          {"filename": {"type": "string"}}),

    _tool("get_arduino_state",
          "Return the Arduino-controlled hardware state (shutter, pellicle, beam splitter, "
          "LED, steering motor step counts, camera) and the valid action names."),
    _tool("arduino_action",
          "Run one Arduino action: open_shutter, close_shutter, insert_pellicle, "
          "remove_pellicle, insert_bs, remove_bs, release_a, release_b.",
          {"action": {"type": "string"}}, ["action"]),
    _tool("move_steering_motor",
          "Move a beam-steering motor by a number of steps: motor 'A' = vertical, "
          "'B' = horizontal. Negative steps move the other way.",
          {"motor": {"type": "string"}, "steps": {"type": "integer"}}, ["motor", "steps"]),
    _tool("set_led", "Set the illumination LED brightness (0-255).",
          {"brightness": {"type": "integer"}}, ["brightness"]),
    _tool("capture_camera_frame",
          "Capture one frame from the sample camera and return it as an image so you can see "
          "the sample (works whether or not the live view is on)."),

    _tool("get_log", "Return the last N controller log lines.",
          {"last_n": {"type": "integer", "default": 20}}),
]


def _image_result(png_b64: str, payload) -> list:
    return [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
        {"type": "text", "text": json.dumps(payload, default=str)},
    ]


def _settings_result(warnings, applied) -> dict:
    out = {"status": "ok", "applied": applied}
    if warnings:
        out["warnings"] = warnings
    return out


def dispatch(controller: MicroscopeController, name: str, args: dict, tabs: dict | None = None):
    tabs = tabs or {}
    controller.clear_stop()

    def tab(key, label):
        t = tabs.get(key)
        if t is None:
            raise LookupError(f"{label} tab not available")
        return t

    try:
        match name:
            case "list_procedures":
                return {"procedures": procedure_loader.list_procedures()}
            case "get_procedure":
                images, text = procedure_loader.load_procedure(args["name"])
                blocks = [{"type": "image", "source": {"type": "base64",
                           "media_type": "image/png", "data": b}} for b in images]
                return blocks + [{"type": "text", "text": text}]

            case "get_state":
                return controller.get_state()
            case "list_instrument_controls":
                return {"controls": tab("controls", "Instrument Controls").list_controls()}
            case "list_instrument_buttons":
                return {"buttons": tab("controls", "Instrument Controls").list_buttons()}
            case "set_instrument_control":
                label = tab("controls", "Instrument Controls").set_control(
                    args["control"], float(args["value"]))
                return {"status": "ok", "control": label, "value": args["value"]}
            case "press_instrument_button":
                return {"status": "ok", **tab("controls", "Instrument Controls")
                        .press_button(args["button"])}

            case "get_2d_scan_settings":
                return tab("2d_scan", "2D Scan").get_settings()
            case "set_2d_scan_settings":
                return _settings_result(tab("2d_scan", "2D Scan").apply_settings(args), args)
            case "run_2d_scan":
                res = tab("2d_scan", "2D Scan").run_scan_blocking()
                if "error" in res:
                    return res
                return _image_result(res["png_b64"], res["stats"])
            case "save_2d_scan":
                return {"status": "saved",
                        "path": tab("2d_scan", "2D Scan").save_data(args.get("filename") or None)}

            case "get_alignment_settings":
                return tab("alignment", "Alignment").get_settings()
            case "set_alignment_settings":
                return _settings_result(tab("alignment", "Alignment").apply_settings(args), args)
            case "run_alignment":
                return tab("alignment", "Alignment").run_alignment_blocking(
                    bool(args.get("set_origin", False)))

            case "get_gate_settings":
                return tab("gate_breakdown", "Gate Breakdown").get_settings()
            case "set_gate_settings":
                return _settings_result(
                    tab("gate_breakdown", "Gate Breakdown").apply_settings(args), args)
            case "set_gate_voltage":
                return tab("gate_breakdown", "Gate Breakdown").set_gate_voltage_blocking(
                    args["gate"], float(args["volts"]))
            case "run_gate_sweep":
                res = tab("gate_breakdown", "Gate Breakdown").run_sweep_blocking()
                if "error" in res:
                    return res
                return _image_result(res["png_b64"], res["stats"])
            case "save_gate_sweep":
                return {"status": "saved", "path": tab("gate_breakdown", "Gate Breakdown")
                        .save_data(args.get("filename") or None)}

            case "get_arduino_state":
                return tab("arduino", "Arduino").get_settings()
            case "arduino_action":
                return tab("arduino", "Arduino").run_action(str(args["action"]))
            case "move_steering_motor":
                return tab("arduino", "Arduino").move_motor(str(args["motor"]), int(args["steps"]))
            case "set_led":
                return tab("arduino", "Arduino").set_led(int(args["brightness"]))
            case "capture_camera_frame":
                b64 = tab("arduino", "Arduino").capture_frame_b64()
                if b64 is None:
                    return {"error": "Could not capture a frame (no camera?)"}
                return _image_result(b64, {"status": "Camera frame captured."})

            case "get_log":
                return {"log": controller.get_log(int(args.get("last_n", 20)))}
            case _:
                return {"error": f"Unknown tool: {name}"}
    except (KeyError, LookupError, ValueError, RuntimeError, FileNotFoundError) as e:
        return {"error": str(e)}
