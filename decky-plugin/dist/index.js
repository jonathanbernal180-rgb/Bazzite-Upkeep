const manifest = {"name":"Upkeep"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const toaster = api.toaster;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

var DefaultContext = {
  color: undefined,
  size: undefined,
  className: undefined,
  style: undefined,
  attr: undefined
};
var IconContext = SP_REACT.createContext && /*#__PURE__*/SP_REACT.createContext(DefaultContext);

var _excluded = ["attr", "size", "title"];
function _objectWithoutProperties(e, t) { if (null == e) return {}; var o, r, i = _objectWithoutPropertiesLoose(e, t); if (Object.getOwnPropertySymbols) { var n = Object.getOwnPropertySymbols(e); for (r = 0; r < n.length; r++) o = n[r], -1 === t.indexOf(o) && {}.propertyIsEnumerable.call(e, o) && (i[o] = e[o]); } return i; }
function _objectWithoutPropertiesLoose(r, e) { if (null == r) return {}; var t = {}; for (var n in r) if ({}.hasOwnProperty.call(r, n)) { if (-1 !== e.indexOf(n)) continue; t[n] = r[n]; } return t; }
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function ownKeys(e, r) { var t = Object.keys(e); if (Object.getOwnPropertySymbols) { var o = Object.getOwnPropertySymbols(e); r && (o = o.filter(function (r) { return Object.getOwnPropertyDescriptor(e, r).enumerable; })), t.push.apply(t, o); } return t; }
function _objectSpread(e) { for (var r = 1; r < arguments.length; r++) { var t = null != arguments[r] ? arguments[r] : {}; r % 2 ? ownKeys(Object(t), true).forEach(function (r) { _defineProperty(e, r, t[r]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function (r) { Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r)); }); } return e; }
function _defineProperty(e, r, t) { return (r = _toPropertyKey(r)) in e ? Object.defineProperty(e, r, { value: t, enumerable: true, configurable: true, writable: true }) : e[r] = t, e; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == typeof i ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != typeof t || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r); if ("object" != typeof i) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
function Tree2Element(tree) {
  return tree && tree.map((node, i) => /*#__PURE__*/SP_REACT.createElement(node.tag, _objectSpread({
    key: i
  }, node.attr), Tree2Element(node.child)));
}
function GenIcon(data) {
  return props => /*#__PURE__*/SP_REACT.createElement(IconBase, _extends({
    attr: _objectSpread({}, data.attr)
  }, props), Tree2Element(data.child));
}
function IconBase(props) {
  var elem = conf => {
    var attr = props.attr,
      size = props.size,
      title = props.title,
      svgProps = _objectWithoutProperties(props, _excluded);
    var computedSize = size || conf.size || "1em";
    var className;
    if (conf.className) className = conf.className;
    if (props.className) className = (className ? className + " " : "") + props.className;
    return /*#__PURE__*/SP_REACT.createElement("svg", _extends({
      stroke: "currentColor",
      fill: "currentColor",
      strokeWidth: "0"
    }, conf.attr, attr, svgProps, {
      className: className,
      style: _objectSpread(_objectSpread({
        color: props.color || conf.color
      }, conf.style), props.style),
      height: computedSize,
      width: computedSize,
      xmlns: "http://www.w3.org/2000/svg"
    }), title && /*#__PURE__*/SP_REACT.createElement("title", null, title), props.children);
  };
  return IconContext !== undefined ? /*#__PURE__*/SP_REACT.createElement(IconContext.Consumer, null, conf => elem(conf)) : elem(DefaultContext);
}

// THIS FILE IS AUTO GENERATED
function FaClipboardCheck (props) {
  return GenIcon({"attr":{"viewBox":"0 0 384 512"},"child":[{"tag":"path","attr":{"d":"M336 64h-80c0-35.3-28.7-64-64-64s-64 28.7-64 64H48C21.5 64 0 85.5 0 112v352c0 26.5 21.5 48 48 48h288c26.5 0 48-21.5 48-48V112c0-26.5-21.5-48-48-48zM192 40c13.3 0 24 10.7 24 24s-10.7 24-24 24-24-10.7-24-24 10.7-24 24-24zm121.2 231.8l-143 141.8c-4.7 4.7-12.3 4.6-17-.1l-82.6-83.3c-4.7-4.7-4.6-12.3.1-17L99.1 285c4.7-4.7 12.3-4.6 17 .1l46 46.4 106-105.2c4.7-4.7 12.3-4.6 17 .1l28.2 28.4c4.7 4.8 4.6 12.3-.1 17z"},"child":[]}]})(props);
}

// ---- backend calls (main.py)
const getReport = callable("get_report");
const getCheck = callable("get_check");
const runNow = callable("run_now");
const getProgress = callable("get_progress");
const rollbackInfo = callable("rollback_info");
const rollbackDecky = callable("rollback_decky");
const checkNow = callable("check_now");
const isRunning = callable("is_running");
const getSchedule = callable("get_schedule");
const setSchedule = callable("set_schedule");
const wasSeen = callable("was_seen");
const markSeen = callable("mark_seen");
const reinstallDecky = callable("reinstall_decky");
const getAction = callable("get_action");
const getSetup = callable("get_setup");
const setDistro = callable("set_distro");
const DISTRO_NAME = { bazzite: "Bazzite", steamos: "SteamOS" };
const FLATPAK_PREVIEW = 6;
const ICON = {
    updated: "✅",
    unchanged: "✅",
    staged: "⏳",
    error: "⚠️",
    rolled_back: "↩️",
    available: "⬆️",
};
const reportKey = (r) => `${r.generated}|${r.health_checked ?? ""}`;
function fmtTime(iso) {
    if (!iso)
        return "";
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}
function changeText(r) {
    switch (r.status) {
        case "unchanged":
            return "No change";
        case "rolled_back":
            return `Kept on ${r.old ?? "previous version"}`;
        case "available":
            if (r.old && r.new)
                return `${r.old} → ${r.new}`;
            return r.new ? `Update available: ${r.new}` : "Update available";
        case "error":
            return r.old ?? "See issues";
    }
    if (r.old && r.new)
        return `${r.old} → ${r.new}`;
    return "Updated";
}
// ---- pieces
const RowItem = ({ row }) => (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
    window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: `${ICON[row.status] ?? "•"} ${row.name}`, description: row.note ? `${changeText(row)} · ${row.note}` : changeText(row) })));
const Note = ({ text }) => (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
    window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: text })));
const IssueItem = ({ issue }) => {
    const [open, setOpen] = SP_REACT.useState(false);
    const lines = [
        issue.problem,
        issue.reason ? `Reason: ${issue.reason}` : null,
        issue.action ? `↩️ ${issue.action}${issue.action_detail ? ` ${issue.action_detail}` : ""}` : null,
        issue.hint ?? null,
    ].filter(Boolean);
    return (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: `⚠️ ${issue.name}`, description: window.SP_REACT.createElement("div", null, lines.map((l, i) => (window.SP_REACT.createElement("div", { key: i }, l)))) })),
        issue.log && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: () => setOpen(!open) }, open ? "Hide full log" : "View full log"))),
        open && issue.log && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement("div", { style: {
                    fontFamily: "monospace",
                    fontSize: "10px",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                    maxHeight: "240px",
                    overflowY: "auto",
                    padding: "6px",
                    background: "rgba(0,0,0,0.35)",
                    borderRadius: "4px",
                } }, issue.log)))));
};
// only = the things you picked; null = everything
async function startUpdate(only, onStart) {
    if (await runNow(only)) {
        onStart("update");
        toaster.toast({
            title: "Upkeep",
            body: only ? "Installing the updates you picked." : "Updating everything. Decky may reload for a moment.",
        });
    }
}
// "Update now" asks first: everything, or pick?
function askUpdate(onStart) {
    let modal;
    modal = DFL.showModal(window.SP_REACT.createElement(DFL.ConfirmModal, { strTitle: "Install updates", strDescription: "Update everything now (system, Flatpak apps, Decky and plugins), or see what's available first and choose which updates to install.", strOKButtonText: "Update all", strMiddleButtonText: "Choose updates", strCancelButtonText: "Cancel", onOK: () => startUpdate(null, onStart), onMiddleButton: async () => {
            modal?.Close();
            if (await checkNow())
                onStart("check");
        } }));
}
const ActionButtons = ({ running, onStart }) => (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
    window.SP_REACT.createElement(DFL.PanelSectionRow, null,
        window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", disabled: running !== null, onClick: () => askUpdate(onStart) }, running === "update" ? "Updating…" : "Update now")),
    window.SP_REACT.createElement(DFL.PanelSectionRow, null,
        window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", disabled: running !== null, onClick: async () => {
                if (await checkNow())
                    onStart("check");
            } }, running === "check" ? "Checking…" : "Check for updates")),
    window.SP_REACT.createElement(DFL.PanelSectionRow, null,
        window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", disabled: running !== null, onClick: () => DFL.showModal(window.SP_REACT.createElement(DFL.ConfirmModal, { strTitle: "Reinstall Decky?", strDescription: "Downloads a fresh copy of the latest Decky. Decky and this menu will close for about a minute, then come back. If the new copy doesn't start, your current version is restored.", strOKButtonText: "Reinstall", strCancelButtonText: "Cancel", onOK: async () => {
                    if (await reinstallDecky()) {
                        onStart("reinstall");
                        toaster.toast({ title: "Upkeep", body: "Reinstalling Decky. Back in about a minute." });
                    }
                } })) }, running === "reinstall" ? "Reinstalling…" : "Reinstall Decky"))));
// Results of "Check for updates" (nothing installed yet). Each update has a
// switch, so you can install all of them or only the ones you leave on.
const AvailableSection = ({ check, running, onStart, }) => {
    const rows = [...check.system, ...check.plugins, ...check.flatpaks].filter((r) => r.status === "available" || r.status === "staged");
    const rt = check.runtimes_updated ?? 0;
    const count = rows.length + (rt > 0 ? 1 : 0);
    const pickable = (r) => !!r.key && r.status === "available" && !r.locked;
    const keys = [...rows.filter(pickable).map((r) => r.key), ...(rt > 0 ? ["runtimes"] : [])];
    const [picked, setPicked] = SP_REACT.useState({});
    SP_REACT.useEffect(() => {
        // Everything starts switched on, except things that are on hold
        const next = {};
        rows.filter(pickable).forEach((r) => (next[r.key] = !r.held));
        if (rt > 0)
            next["runtimes"] = true;
        setPicked(next);
    }, [check.generated]);
    const chosen = keys.filter((k) => picked[k]);
    const toggle = (k) => (on) => setPicked((p) => ({ ...p, [k]: on }));
    return (window.SP_REACT.createElement(DFL.PanelSection, { title: `Update check · ${fmtTime(check.generated)}` },
        window.SP_REACT.createElement(Note, { text: count === 0 ? "✅ Everything is up to date" : `⬆️ ${count} update${count !== 1 ? "s" : ""} available` }),
        check.issues.map((i, k) => (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: `i${k}` },
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: `⚠️ ${i.name}`, description: i.reason ? `${i.problem}: ${i.reason}` : i.problem })))),
        keys.length > 0 && window.SP_REACT.createElement(Note, { text: "Nothing changed yet. Switch off anything you want to skip." }),
        rows.map((r, k) => pickable(r) ? (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: k },
            window.SP_REACT.createElement(DFL.ToggleField, { bottomSeparator: "none", label: r.name, description: r.note ? `${changeText(r)} · ${r.note}` : changeText(r), checked: !!picked[r.key], onChange: toggle(r.key) }))) : (window.SP_REACT.createElement(RowItem, { key: k, row: r }))),
        rt > 0 && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ToggleField, { bottomSeparator: "none", label: "System runtimes", description: `${rt} to update · shared parts your apps run on`, checked: !!picked["runtimes"], onChange: toggle("runtimes") }))),
        keys.length > 0 && (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", disabled: running !== null || chosen.length === 0, onClick: () => startUpdate(chosen, onStart) }, `Install selected (${chosen.length} of ${keys.length})`)),
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", disabled: running !== null, onClick: () => startUpdate(null, onStart) }, "Update all"))))));
};
// What the update that's running is doing, with a percentage beside each item
const STATE_ICON = { waiting: "•", working: "⏳", done: "✅", error: "⚠️", skipped: "•" };
function progressText(i) {
    switch (i.state) {
        case "working":
            return i.percent != null ? `${i.percent}%` : "Working…";
        case "done":
            return "Done";
        case "error":
            return "Failed";
        case "skipped":
            return "Skipped";
    }
    return "Waiting";
}
const ProgressSection = ({ progress }) => {
    if (!progress || progress.items.length === 0) {
        return (window.SP_REACT.createElement(DFL.PanelSection, { title: "Updating now" },
            window.SP_REACT.createElement(Note, { text: "\u23F3 Starting\u2026" })));
    }
    const finished = progress.items.filter((i) => ["done", "error", "skipped"].includes(i.state)).length;
    return (window.SP_REACT.createElement(DFL.PanelSection, { title: "Updating now" },
        window.SP_REACT.createElement(Note, { text: `⏳ ${finished} of ${progress.items.length} finished` }),
        progress.items.map((i) => (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: i.key },
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: `${STATE_ICON[i.state] ?? "•"} ${i.name}`, description: i.detail ?? undefined }, progressText(i)))))));
};
// Schedule settings
const FREQUENCIES = [
    { data: "daily", label: "Daily" },
    { data: "every_other_day", label: "Every other day" },
    { data: "weekly", label: "Weekly" },
    { data: "manual", label: "Manual only" },
];
const DAYS = [
    { data: "Sun", label: "Sunday" },
    { data: "Mon", label: "Monday" },
    { data: "Tue", label: "Tuesday" },
    { data: "Wed", label: "Wednesday" },
    { data: "Thu", label: "Thursday" },
    { data: "Fri", label: "Friday" },
    { data: "Sat", label: "Saturday" },
];
const HOURS = Array.from({ length: 24 }, (_, h) => ({
    data: h,
    label: `${h % 12 === 0 ? 12 : h % 12} ${h < 12 ? "AM" : "PM"}`,
}));
const MINUTES = [0, 15, 30, 45].map((m) => ({ data: m, label: `:${String(m).padStart(2, "0")}` }));
const ScheduleSection = () => {
    const [s, setS] = SP_REACT.useState(null);
    SP_REACT.useEffect(() => {
        getSchedule().then(setS).catch((e) => console.error("Upkeep", e));
    }, []);
    if (!s)
        return null;
    const save = async (patch) => {
        const next = { ...s, ...patch };
        setS(next);
        try {
            setS(await setSchedule(next.frequency, next.hour, next.minute, next.weekday));
        }
        catch (e) {
            console.error("Upkeep", e);
            toaster.toast({ title: "Upkeep", body: "Couldn't save the schedule" });
        }
    };
    return (window.SP_REACT.createElement(DFL.PanelSection, { title: "Schedule" },
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.DropdownItem, { label: "How often", rgOptions: FREQUENCIES, selectedOption: s.frequency, onChange: (o) => save({ frequency: o.data }) })),
        s.frequency === "weekly" && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.DropdownItem, { label: "Day", rgOptions: DAYS, selectedOption: s.weekday, onChange: (o) => save({ weekday: o.data }) }))),
        s.frequency !== "manual" && (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.DropdownItem, { label: "Hour", rgOptions: HOURS, selectedOption: s.hour, onChange: (o) => save({ hour: o.data }) })),
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.DropdownItem, { label: "Minute", rgOptions: MINUTES, selectedOption: s.minute, onChange: (o) => save({ minute: o.data }) })))),
        window.SP_REACT.createElement(Note, { text: s.frequency === "manual"
                ? "Automatic updates are off. Use Update now."
                : s.next_run
                    ? `Next run: ${fmtTime(s.next_run)}`
                    : "Next run: not scheduled yet" })));
};
// A command shown for typing into Konsole
const CMD_STYLE = {
    fontFamily: "monospace",
    fontSize: "11px",
    wordBreak: "break-all",
    marginTop: "4px",
    padding: "4px 6px",
    background: "rgba(0,0,0,0.35)",
    borderRadius: "4px",
};
function workarounds(setup) {
    const c = setup.cli;
    const list = [];
    if (setup.distro === "steamos") {
        list.push({
            title: "sudo asks for a password you never set",
            text: "SteamOS has no password by default. Set one once:",
            cmd: "passwd",
        });
    }
    list.push({ title: "Decky is missing or won't open", text: "Switch to Desktop Mode, open Konsole and run:", cmd: `sudo ${c} reinstall-decky` }, { title: "A Decky update broke something", text: "Goes back to the Decky version you had before:", cmd: `sudo ${c} rollback-decky` }, { title: "See the latest report without Decky", text: "In Konsole run the command below, or open ~/upkeep/latest.txt", cmd: `${c} show` }, { title: "Update manually", text: "Same as Update now:", cmd: `sudo ${c} run --manual` }, { title: "Check for updates manually", text: "Same as Check for updates (installs nothing):", cmd: `sudo ${c} check` });
    if (setup.distro === "bazzite") {
        list.push({
            title: "Game Mode update stuck at 100%",
            text: "Skip Steam's update button and use Update now, or run:",
            cmd: `sudo ${c} run --manual`,
        }, {
            title: "A system update broke something",
            text: "Restart and pick the previous entry in the boot menu, or run this and restart:",
            cmd: "sudo rpm-ostree rollback",
        });
    }
    else {
        list.push({
            title: "A system update broke something",
            text: "Restart and choose the previous version in the SteamOS boot menu. On Steam Deck, hold the ••• button while turning it on.",
        });
    }
    list.push({
        title: "A plugin broke and wasn't fixed",
        text: "Backups are in ~/upkeep/backups/<date>/plugins/. Replace the broken folder with the backup:",
        cmd: "sudo rm -rf ~/homebrew/plugins/<name> && sudo cp -a ~/upkeep/backups/<date>/plugins/<name> ~/homebrew/plugins/ && sudo systemctl restart plugin_loader",
    }, {
        title: "Turn off automatic updates without Decky",
        text: "Stops the schedule (turn back on with enable --now):",
        cmd: "sudo systemctl disable --now upkeep-run.timer",
    }, { title: "Watch what upkeep is doing", text: "Shows the live log:", cmd: "journalctl -fu upkeep-run -u upkeep-manual" });
    return list;
}
const WorkaroundsSection = ({ setup }) => (window.SP_REACT.createElement(DFL.PanelSection, { title: "Workarounds" },
    window.SP_REACT.createElement(Note, { text: "Use these in Desktop Mode \u2192 Konsole when a button can't help." }),
    workarounds(setup).map((w, k) => (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: k },
        window.SP_REACT.createElement(DFL.Field, { focusable: true, label: w.title, description: window.SP_REACT.createElement("div", null,
                window.SP_REACT.createElement("div", null, w.text),
                w.cmd && window.SP_REACT.createElement("div", { style: CMD_STYLE }, w.cmd)) }))))));
// "Think the new Decky update broke something?" -> its own page
const RollbackSection = ({ onOpen }) => (window.SP_REACT.createElement(DFL.PanelSection, { title: "Decky problems" },
    window.SP_REACT.createElement(DFL.PanelSectionRow, null,
        window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "Think the new Decky update broke something?", description: "You can go back to the Decky version you had before." })),
    window.SP_REACT.createElement(DFL.PanelSectionRow, null,
        window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: onOpen }, "Roll back Decky"))));
const RollbackPage = ({ setup, running, onStart, onBack, }) => {
    // undefined = still looking, null = couldn't find out
    const [info, setInfo] = SP_REACT.useState(undefined);
    SP_REACT.useEffect(() => {
        rollbackInfo()
            .then(setInfo)
            .catch((e) => {
            console.error("Upkeep", e);
            setInfo(null);
        });
    }, []);
    const target = info?.target ?? null;
    const cur = info?.current ?? "your current version";
    return (window.SP_REACT.createElement(DFL.PanelSection, { title: "Roll back Decky" },
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "Think the new Decky update broke something?", description: "If plugins stopped loading, or this menu started misbehaving right after Decky updated, Upkeep can put back the Decky version you had before." })),
        info === undefined && window.SP_REACT.createElement(Note, { text: "Looking for an earlier version\u2026" }),
        info === null && window.SP_REACT.createElement(Note, { text: "\u26A0\uFE0F Couldn't check. Is the Upkeep script installed?" }),
        info && (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "Installed now" }, info.current ?? "Unknown")),
            info.held && (window.SP_REACT.createElement(Note, { text: `Upkeep is already holding Decky back from ${info.held} after an earlier rollback.` })),
            target ? (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
                window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                    window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "Goes back to", description: target.source === "backup"
                            ? `The copy Upkeep saved${target.saved ? ` on ${fmtTime(target.saved)}` : ""}`
                            : "Downloaded from Decky's own releases (no saved copy on this PC)" }, target.version)),
                window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                    window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "What happens", description: window.SP_REACT.createElement("div", null,
                            window.SP_REACT.createElement("div", null,
                                "1. Saves a copy of ",
                                cur,
                                "."),
                            window.SP_REACT.createElement("div", null,
                                "2. Puts ",
                                target.version,
                                " back and restarts Decky. This menu closes for about a minute."),
                            window.SP_REACT.createElement("div", null,
                                "3. If ",
                                target.version,
                                " doesn't start, ",
                                cur,
                                " is restored."),
                            window.SP_REACT.createElement("div", null,
                                "4. Upkeep then leaves Decky alone until a release newer than ",
                                cur,
                                " comes out."),
                            window.SP_REACT.createElement("div", null, "Changed your mind later? Reinstall Decky puts the newest version back.")) })),
                window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                    window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", disabled: running !== null, onClick: async () => {
                            if (await rollbackDecky()) {
                                onStart("rollback");
                                toaster.toast({
                                    title: "Upkeep",
                                    body: `Rolling Decky back to ${target.version}. Back in about a minute.`,
                                });
                                onBack();
                            }
                        } }, `Roll back to ${target.version}`)))) : (window.SP_REACT.createElement(Note, { text: "No earlier Decky version is available to go back to." })),
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "If Decky won't open at all", description: window.SP_REACT.createElement("div", null,
                        window.SP_REACT.createElement("div", null, "Do the same thing from Desktop Mode \u2192 Konsole:"),
                        window.SP_REACT.createElement("div", { style: CMD_STYLE }, `sudo ${setup.cli} rollback-decky`)) })))),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: onBack }, "Back"))));
};
// First-run setup (and "Change distro")
const SetupPage = ({ setup, changing, onDone, onCancel, }) => {
    const choose = async (d) => {
        const apply = async () => onDone(await setDistro(d));
        if (setup.detected && setup.detected !== d) {
            DFL.showModal(window.SP_REACT.createElement(DFL.ConfirmModal, { strTitle: `This doesn't look like ${DISTRO_NAME[d]}`, strDescription: `This PC looks like ${DISTRO_NAME[setup.detected]}. If you pick ${DISTRO_NAME[d]}, system updates will use the wrong commands and fail. Use ${DISTRO_NAME[d]} anyway?`, strOKButtonText: `Use ${DISTRO_NAME[d]}`, strCancelButtonText: "Go back", onOK: apply }));
        }
        else {
            await apply();
        }
    };
    const option = (d) => `${DISTRO_NAME[d]}${setup.detected === d ? " (detected)" : ""}${changing && setup.distro === d ? " · current" : ""}`;
    return (window.SP_REACT.createElement(DFL.PanelSection, { title: changing ? "Change distro" : "Welcome to Upkeep" },
        !changing && (window.SP_REACT.createElement(Note, { text: "Keeps your system, Flatpaks, Decky and plugins updated, then checks that everything still works." })),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "\u2139\uFE0F Made for Bazzite", description: "Upkeep is designed specifically for Bazzite, and built to be compatible with SteamOS." })),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "Which system are you running?", description: setup.detected
                    ? `Detected: ${DISTRO_NAME[setup.detected]}`
                    : "Couldn't detect it automatically. Pick the one you installed." })),
        ["bazzite", "steamos"].map((d) => (window.SP_REACT.createElement(DFL.PanelSectionRow, { key: d },
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: () => choose(d) }, option(d))))),
        window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "What changes", description: "System updates use rpm-ostree on Bazzite and steamos-update on SteamOS. Flatpaks, Decky, plugins and reports work the same on both." })),
        !setup.installed && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: "\u26A0\uFE0F Upkeep script not installed", description: "In Desktop Mode, run ./install.sh from the bazzite-upkeep folder, then come back here." }))),
        changing && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
            window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: onCancel }, "Cancel")))));
};
const ChangeDistroSection = ({ setup, onChange }) => (window.SP_REACT.createElement(DFL.PanelSection, { title: "Setup" },
    window.SP_REACT.createElement(Note, { text: `System: ${DISTRO_NAME[setup.distro]}` }),
    window.SP_REACT.createElement(DFL.PanelSectionRow, null,
        window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: onChange }, "Change distro"))));
// ---- main panel
const Content = () => {
    const [report, setReport] = SP_REACT.useState(undefined);
    const [check, setCheck] = SP_REACT.useState(null);
    const [running, setRunning] = SP_REACT.useState(null);
    const [allFlatpaks, setAllFlatpaks] = SP_REACT.useState(false);
    const [setup, setSetup] = SP_REACT.useState(null);
    const [changing, setChanging] = SP_REACT.useState(false);
    const [rollback, setRollback] = SP_REACT.useState(false);
    const [progress, setProgress] = SP_REACT.useState(null);
    const refresh = async () => {
        try {
            setReport(await getReport());
            setCheck(await getCheck());
            setRunning(await isRunning());
        }
        catch (e) {
            console.error("Upkeep", e);
            setReport(null);
        }
    };
    SP_REACT.useEffect(() => {
        getSetup()
            .then(setSetup)
            .catch((e) => console.error("Upkeep", e));
        refresh();
        const t = setInterval(refresh, 5000);
        return () => clearInterval(t);
    }, []);
    SP_REACT.useEffect(() => {
        if (report)
            markSeen(reportKey(report), "report");
    }, [report?.generated, report?.health_checked]);
    // While an update runs, read its progress every second
    SP_REACT.useEffect(() => {
        if (running !== "update") {
            setProgress(null);
            return;
        }
        let live = true;
        const tick = async () => {
            try {
                const p = await getProgress();
                if (live)
                    setProgress(p);
            }
            catch (e) {
                console.error("Upkeep", e);
            }
        };
        tick();
        const t = setInterval(tick, 1000);
        return () => {
            live = false;
            clearInterval(t);
        };
    }, [running]);
    if (report === undefined || setup === null) {
        return (window.SP_REACT.createElement(DFL.PanelSection, null,
            window.SP_REACT.createElement(Note, { text: "Loading\u2026" })));
    }
    if (!setup.done || changing) {
        return (window.SP_REACT.createElement(SetupPage, { setup: setup, changing: changing, onDone: (s) => {
                setSetup(s);
                setChanging(false);
            }, onCancel: () => setChanging(false) }));
    }
    if (rollback) {
        return window.SP_REACT.createElement(RollbackPage, { setup: setup, running: running, onStart: setRunning, onBack: () => setRollback(false) });
    }
    // Only show a check result if it's newer than the last update run
    const freshCheck = check && (!report || new Date(check.generated) > new Date(report.generated)) ? check : null;
    // Shown under the buttons: live progress during an update, otherwise the update check
    const live = running === "update" ? (window.SP_REACT.createElement(ProgressSection, { progress: progress })) : (freshCheck && window.SP_REACT.createElement(AvailableSection, { check: freshCheck, running: running, onStart: setRunning }));
    if (report === null) {
        return (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
            window.SP_REACT.createElement(DFL.PanelSection, { title: "Upkeep" },
                window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                    window.SP_REACT.createElement(DFL.Field, { focusable: true, label: "No report yet", description: "Runs on your schedule, or update now." })),
                running === "rollback" && window.SP_REACT.createElement(Note, { text: "\u21A9\uFE0F Rolling Decky back\u2026" }),
                window.SP_REACT.createElement(ActionButtons, { running: running, onStart: setRunning })),
            live,
            window.SP_REACT.createElement(RollbackSection, { onOpen: () => setRollback(true) }),
            window.SP_REACT.createElement(ScheduleSection, null),
            window.SP_REACT.createElement(ChangeDistroSection, { setup: setup, onChange: () => setChanging(true) }),
            window.SP_REACT.createElement(WorkaroundsSection, { setup: setup })));
    }
    const n = report.issues.length;
    const changedPlugins = report.plugins.filter((p) => p.status !== "unchanged");
    const samePlugins = report.plugins.length - changedPlugins.length;
    const flatpaks = allFlatpaks ? report.flatpaks : report.flatpaks.slice(0, FLATPAK_PREVIEW);
    const hiddenFlatpaks = report.flatpaks.length - flatpaks.length;
    const rt = report.runtimes_updated ?? 0;
    return (window.SP_REACT.createElement(window.SP_REACT.Fragment, null,
        window.SP_REACT.createElement(DFL.PanelSection, { title: fmtTime(report.generated) },
            window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.Field, { focusable: true, bottomSeparator: "none", label: n === 0
                        ? report.partial
                            ? "✅ Selected updates installed and working"
                            : "✅ Everything updated and working"
                        : `⚠️ ${n} issue${n > 1 ? "s need" : " needs"} a look` })),
            running === "rollback" && window.SP_REACT.createElement(Note, { text: "\u21A9\uFE0F Rolling Decky back\u2026" }),
            window.SP_REACT.createElement(ActionButtons, { running: running, onStart: setRunning })),
        live,
        n > 0 && (window.SP_REACT.createElement(DFL.PanelSection, { title: "Issues" }, report.issues.map((i, k) => (window.SP_REACT.createElement(IssueItem, { key: k, issue: i }))))),
        window.SP_REACT.createElement(DFL.PanelSection, { title: "System" }, report.system.map((r, k) => (window.SP_REACT.createElement(RowItem, { key: k, row: r })))),
        window.SP_REACT.createElement(DFL.PanelSection, { title: "Decky Plugins" },
            changedPlugins.map((r, k) => (window.SP_REACT.createElement(RowItem, { key: k, row: r }))),
            samePlugins > 0 && (window.SP_REACT.createElement(Note, { text: `${changedPlugins.length === 0 && samePlugins > 1 ? "All " : ""}${samePlugins} plugin${samePlugins !== 1 ? "s" : ""} already up to date` })),
            report.plugins.length === 0 && window.SP_REACT.createElement(Note, { text: "No plugins installed" })),
        window.SP_REACT.createElement(DFL.PanelSection, { title: "Flatpaks" },
            flatpaks.map((r, k) => (window.SP_REACT.createElement(RowItem, { key: k, row: r }))),
            report.flatpaks.length === 0 && window.SP_REACT.createElement(Note, { text: "No app updates" }),
            hiddenFlatpaks > 0 && (window.SP_REACT.createElement(DFL.PanelSectionRow, null,
                window.SP_REACT.createElement(DFL.ButtonItem, { layout: "below", onClick: () => setAllFlatpaks(true) }, `Show ${hiddenFlatpaks} more`))),
            rt > 0 && window.SP_REACT.createElement(Note, { text: `+ ${rt} system runtime${rt !== 1 ? "s" : ""} updated` })),
        report.health.length > 0 && (window.SP_REACT.createElement(DFL.PanelSection, { title: "Health Check" },
            report.health.map((h, k) => (window.SP_REACT.createElement(Note, { key: k, text: `${h.ok ? "✅" : "⚠️"} ${h.text}` }))),
            report.health_checked && window.SP_REACT.createElement(Note, { text: `Checked ${fmtTime(report.health_checked)}` }))),
        window.SP_REACT.createElement(RollbackSection, { onOpen: () => setRollback(true) }),
        window.SP_REACT.createElement(ScheduleSection, null),
        window.SP_REACT.createElement(ChangeDistroSection, { setup: setup, onChange: () => setChanging(true) }),
        window.SP_REACT.createElement(WorkaroundsSection, { setup: setup })));
};
var index = definePlugin(() => {
    // After a reinstall, Decky reloads: say how it went (once, if recent)
    (async () => {
        try {
            const a = await getAction();
            if (!a || Date.now() - new Date(a.time).getTime() > 15 * 60 * 1000)
                return;
            if (await wasSeen(a.time, "action"))
                return;
            await markSeen(a.time, "action");
            toaster.toast({ title: "Upkeep", body: `${a.ok ? "✅" : "⚠️"} ${a.message}` });
        }
        catch (e) {
            console.error("Upkeep", e);
        }
    })();
    // Pop a toast once per report if something needs attention
    (async () => {
        try {
            const r = await getReport();
            if (!r || r.issues.length === 0)
                return;
            if (await wasSeen(reportKey(r), "report"))
                return;
            const n = r.issues.length;
            toaster.toast({
                title: "Upkeep",
                body: `⚠️ ${n} issue${n > 1 ? "s" : ""}: open Upkeep for details`,
            });
        }
        catch (e) {
            console.error("Upkeep", e);
        }
    })();
    return {
        name: "Upkeep",
        titleView: window.SP_REACT.createElement("div", { className: DFL.staticClasses.Title }, "Upkeep"),
        content: window.SP_REACT.createElement(Content, null),
        icon: window.SP_REACT.createElement(FaClipboardCheck, null),
        onDismount() { },
    };
});

export { index as default };
//# sourceMappingURL=index.js.map
