import {
  ButtonItem,
  ConfirmModal,
  DropdownItem,
  Field,
  PanelSection,
  PanelSectionRow,
  ToggleField,
  showModal,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { FC, useEffect, useState } from "react";
import { FaClipboardCheck } from "react-icons/fa";

// ---- types (match ~/upkeep/latest.json written by upkeep.py)
type Row = {
  name: string;
  old?: string | null;
  new?: string | null;
  status: string;
  note?: string | null;
  key?: string | null; // sent back to install just this one
  held?: boolean; // on hold: left switched off unless you pick it
  locked?: boolean; // on hold in upkeep.conf: can't be picked here
};
type Issue = {
  name: string;
  problem: string;
  reason?: string | null;
  action?: string | null;
  action_detail?: string | null;
  hint?: string | null;
  log?: string | null;
};
type Health = { ok: boolean; text: string };
type Report = {
  kind?: string;
  partial?: boolean; // only the updates you picked were installed
  generated: string;
  health_checked?: string | null;
  issues: Issue[];
  system: Row[];
  plugins: Row[];
  flatpaks: Row[];
  runtimes_updated: number;
  health: Health[];
};

type Schedule = {
  frequency: string;
  hour: number;
  minute: number;
  weekday: string;
  next_run?: string | null;
};
type Running = "update" | "check" | "reinstall" | "rollback" | null;
type Distro = "bazzite" | "steamos";
type Setup = { done: boolean; distro: Distro; detected: Distro | null; installed: boolean; cli: string };
type Action = { action: string; ok: boolean; message: string; time: string };
// ~/upkeep/progress.json, written by upkeep.py while an update runs
type ProgressItem = {
  key: string;
  name: string;
  group: string;
  state: string; // waiting | working | done | error | skipped
  percent?: number | null;
  detail?: string | null;
};
type Progress = { kind: string; running: boolean; started: string; updated: string; items: ProgressItem[] };
type RollbackInfo = {
  current: string | null;
  target: { version: string; source: "backup" | "download"; saved?: string | null } | null;
  held?: string | null;
};

// ---- backend calls (main.py)
const getReport = callable<[], Report | null>("get_report");
const getCheck = callable<[], Report | null>("get_check");
const runNow = callable<[string[] | null], boolean>("run_now");
const getProgress = callable<[], Progress | null>("get_progress");
const rollbackInfo = callable<[], RollbackInfo | null>("rollback_info");
const rollbackDecky = callable<[], boolean>("rollback_decky");
const checkNow = callable<[], boolean>("check_now");
const isRunning = callable<[], Running>("is_running");
const getSchedule = callable<[], Schedule>("get_schedule");
const setSchedule = callable<[string, number, number, string], Schedule>("set_schedule");
const wasSeen = callable<[string, string], boolean>("was_seen");
const markSeen = callable<[string, string], void>("mark_seen");
const reinstallDecky = callable<[], boolean>("reinstall_decky");
const getAction = callable<[], Action | null>("get_action");
const getSetup = callable<[], Setup>("get_setup");
const setDistro = callable<[Distro], Setup>("set_distro");

const DISTRO_NAME: Record<Distro, string> = { bazzite: "Bazzite", steamos: "SteamOS" };

const FLATPAK_PREVIEW = 6;
const ICON: Record<string, string> = {
  updated: "✅",
  unchanged: "✅",
  staged: "⏳",
  error: "⚠️",
  rolled_back: "↩️",
  available: "⬆️",
};

const reportKey = (r: Report) => `${r.generated}|${r.health_checked ?? ""}`;

function fmtTime(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function changeText(r: Row): string {
  switch (r.status) {
    case "unchanged":
      return "No change";
    case "rolled_back":
      return `Kept on ${r.old ?? "previous version"}`;
    case "available":
      if (r.old && r.new) return `${r.old} → ${r.new}`;
      return r.new ? `Update available: ${r.new}` : "Update available";
    case "error":
      return r.old ?? "See issues";
  }
  if (r.old && r.new) return `${r.old} → ${r.new}`;
  return "Updated";
}

// ---- pieces
const RowItem: FC<{ row: Row }> = ({ row }) => (
  <PanelSectionRow>
    <Field
      focusable
      bottomSeparator="none"
      label={`${ICON[row.status] ?? "•"} ${row.name}`}
      description={row.note ? `${changeText(row)} · ${row.note}` : changeText(row)}
    />
  </PanelSectionRow>
);

const Note: FC<{ text: string }> = ({ text }) => (
  <PanelSectionRow>
    <Field focusable bottomSeparator="none" label={text} />
  </PanelSectionRow>
);

const IssueItem: FC<{ issue: Issue }> = ({ issue }) => {
  const [open, setOpen] = useState(false);
  const lines = [
    issue.problem,
    issue.reason ? `Reason: ${issue.reason}` : null,
    issue.action ? `↩️ ${issue.action}${issue.action_detail ? ` ${issue.action_detail}` : ""}` : null,
    issue.hint ?? null,
  ].filter(Boolean) as string[];

  return (
    <>
      <PanelSectionRow>
        <Field
          focusable
          bottomSeparator="none"
          label={`⚠️ ${issue.name}`}
          description={
            <div>
              {lines.map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          }
        />
      </PanelSectionRow>
      {issue.log && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => setOpen(!open)}>
            {open ? "Hide full log" : "View full log"}
          </ButtonItem>
        </PanelSectionRow>
      )}
      {open && issue.log && (
        <PanelSectionRow>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "10px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: "240px",
              overflowY: "auto",
              padding: "6px",
              background: "rgba(0,0,0,0.35)",
              borderRadius: "4px",
            }}
          >
            {issue.log}
          </div>
        </PanelSectionRow>
      )}
    </>
  );
};

// only = the things you picked; null = everything
async function startUpdate(only: string[] | null, onStart: (k: Running) => void) {
  if (await runNow(only)) {
    onStart("update");
    toaster.toast({
      title: "Upkeep",
      body: only ? "Installing the updates you picked." : "Updating everything. Decky may reload for a moment.",
    });
  }
}

// "Update now" asks first: everything, or pick?
function askUpdate(onStart: (k: Running) => void) {
  let modal: { Close: () => void } | undefined;
  modal = showModal(
    <ConfirmModal
      strTitle="Install updates"
      strDescription="Update everything now (system, Flatpak apps, Decky and plugins), or see what's available first and choose which updates to install."
      strOKButtonText="Update all"
      strMiddleButtonText="Choose updates"
      strCancelButtonText="Cancel"
      onOK={() => startUpdate(null, onStart)}
      onMiddleButton={async () => {
        modal?.Close();
        if (await checkNow()) onStart("check");
      }}
    />,
  );
}

const ActionButtons: FC<{ running: Running; onStart: (k: Running) => void }> = ({ running, onStart }) => (
  <>
    <PanelSectionRow>
      <ButtonItem layout="below" disabled={running !== null} onClick={() => askUpdate(onStart)}>
        {running === "update" ? "Updating…" : "Update now"}
      </ButtonItem>
    </PanelSectionRow>
    <PanelSectionRow>
      <ButtonItem
        layout="below"
        disabled={running !== null}
        onClick={async () => {
          if (await checkNow()) onStart("check");
        }}
      >
        {running === "check" ? "Checking…" : "Check for updates"}
      </ButtonItem>
    </PanelSectionRow>
    <PanelSectionRow>
      <ButtonItem
        layout="below"
        disabled={running !== null}
        onClick={() =>
          showModal(
            <ConfirmModal
              strTitle="Reinstall Decky?"
              strDescription="Downloads a fresh copy of the latest Decky. Decky and this menu will close for about a minute, then come back. If the new copy doesn't start, your current version is restored."
              strOKButtonText="Reinstall"
              strCancelButtonText="Cancel"
              onOK={async () => {
                if (await reinstallDecky()) {
                  onStart("reinstall");
                  toaster.toast({ title: "Upkeep", body: "Reinstalling Decky. Back in about a minute." });
                }
              }}
            />,
          )
        }
      >
        {running === "reinstall" ? "Reinstalling…" : "Reinstall Decky"}
      </ButtonItem>
    </PanelSectionRow>
  </>
);

// Results of "Check for updates" (nothing installed yet). Each update has a
// switch, so you can install all of them or only the ones you leave on.
const AvailableSection: FC<{ check: Report; running: Running; onStart: (k: Running) => void }> = ({
  check,
  running,
  onStart,
}) => {
  const rows = [...check.system, ...check.plugins, ...check.flatpaks].filter(
    (r) => r.status === "available" || r.status === "staged",
  );
  const rt = check.runtimes_updated ?? 0;
  const count = rows.length + (rt > 0 ? 1 : 0);
  const pickable = (r: Row) => !!r.key && r.status === "available" && !r.locked;
  const keys = [...rows.filter(pickable).map((r) => r.key as string), ...(rt > 0 ? ["runtimes"] : [])];

  const [picked, setPicked] = useState<Record<string, boolean>>({});
  useEffect(() => {
    // Everything starts switched on, except things that are on hold
    const next: Record<string, boolean> = {};
    rows.filter(pickable).forEach((r) => (next[r.key as string] = !r.held));
    if (rt > 0) next["runtimes"] = true;
    setPicked(next);
  }, [check.generated]);

  const chosen = keys.filter((k) => picked[k]);
  const toggle = (k: string) => (on: boolean) => setPicked((p) => ({ ...p, [k]: on }));

  return (
    <PanelSection title={`Update check · ${fmtTime(check.generated)}`}>
      <Note text={count === 0 ? "✅ Everything is up to date" : `⬆️ ${count} update${count !== 1 ? "s" : ""} available`} />
      {check.issues.map((i, k) => (
        <PanelSectionRow key={`i${k}`}>
          <Field focusable bottomSeparator="none" label={`⚠️ ${i.name}`} description={i.reason ? `${i.problem}: ${i.reason}` : i.problem} />
        </PanelSectionRow>
      ))}
      {keys.length > 0 && <Note text="Nothing changed yet. Switch off anything you want to skip." />}
      {rows.map((r, k) =>
        pickable(r) ? (
          <PanelSectionRow key={k}>
            <ToggleField
              bottomSeparator="none"
              label={r.name}
              description={r.note ? `${changeText(r)} · ${r.note}` : changeText(r)}
              checked={!!picked[r.key as string]}
              onChange={toggle(r.key as string)}
            />
          </PanelSectionRow>
        ) : (
          <RowItem key={k} row={r} />
        ),
      )}
      {rt > 0 && (
        <PanelSectionRow>
          <ToggleField
            bottomSeparator="none"
            label="System runtimes"
            description={`${rt} to update · shared parts your apps run on`}
            checked={!!picked["runtimes"]}
            onChange={toggle("runtimes")}
          />
        </PanelSectionRow>
      )}
      {keys.length > 0 && (
        <>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={running !== null || chosen.length === 0}
              onClick={() => startUpdate(chosen, onStart)}
            >
              {`Install selected (${chosen.length} of ${keys.length})`}
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" disabled={running !== null} onClick={() => startUpdate(null, onStart)}>
              Update all
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
};

// What the update that's running is doing, with a percentage beside each item
const STATE_ICON: Record<string, string> = { waiting: "•", working: "⏳", done: "✅", error: "⚠️", skipped: "•" };

function progressText(i: ProgressItem): string {
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

const ProgressSection: FC<{ progress: Progress | null }> = ({ progress }) => {
  if (!progress || progress.items.length === 0) {
    return (
      <PanelSection title="Updating now">
        <Note text="⏳ Starting…" />
      </PanelSection>
    );
  }
  const finished = progress.items.filter((i) => ["done", "error", "skipped"].includes(i.state)).length;
  return (
    <PanelSection title="Updating now">
      <Note text={`⏳ ${finished} of ${progress.items.length} finished`} />
      {progress.items.map((i) => (
        <PanelSectionRow key={i.key}>
          <Field
            focusable
            bottomSeparator="none"
            label={`${STATE_ICON[i.state] ?? "•"} ${i.name}`}
            description={i.detail ?? undefined}
          >
            {progressText(i)}
          </Field>
        </PanelSectionRow>
      ))}
    </PanelSection>
  );
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

const ScheduleSection: FC = () => {
  const [s, setS] = useState<Schedule | null>(null);

  useEffect(() => {
    getSchedule().then(setS).catch((e) => console.error("Upkeep", e));
  }, []);

  if (!s) return null;

  const save = async (patch: Partial<Schedule>) => {
    const next = { ...s, ...patch };
    setS(next);
    try {
      setS(await setSchedule(next.frequency, next.hour, next.minute, next.weekday));
    } catch (e) {
      console.error("Upkeep", e);
      toaster.toast({ title: "Upkeep", body: "Couldn't save the schedule" });
    }
  };

  return (
    <PanelSection title="Schedule">
      <PanelSectionRow>
        <DropdownItem
          label="How often"
          rgOptions={FREQUENCIES}
          selectedOption={s.frequency}
          onChange={(o: { data: any }) => save({ frequency: o.data })}
        />
      </PanelSectionRow>
      {s.frequency === "weekly" && (
        <PanelSectionRow>
          <DropdownItem label="Day" rgOptions={DAYS} selectedOption={s.weekday} onChange={(o: { data: any }) => save({ weekday: o.data })} />
        </PanelSectionRow>
      )}
      {s.frequency !== "manual" && (
        <>
          <PanelSectionRow>
            <DropdownItem label="Hour" rgOptions={HOURS} selectedOption={s.hour} onChange={(o: { data: any }) => save({ hour: o.data })} />
          </PanelSectionRow>
          <PanelSectionRow>
            <DropdownItem label="Minute" rgOptions={MINUTES} selectedOption={s.minute} onChange={(o: { data: any }) => save({ minute: o.data })} />
          </PanelSectionRow>
        </>
      )}
      <Note
        text={
          s.frequency === "manual"
            ? "Automatic updates are off. Use Update now."
            : s.next_run
              ? `Next run: ${fmtTime(s.next_run)}`
              : "Next run: not scheduled yet"
        }
      />
    </PanelSection>
  );
};

// A command shown for typing into Konsole
const CMD_STYLE = {
  fontFamily: "monospace",
  fontSize: "11px",
  wordBreak: "break-all" as const,
  marginTop: "4px",
  padding: "4px 6px",
  background: "rgba(0,0,0,0.35)",
  borderRadius: "4px",
};

// Read-only help: what to do when a button can't help (e.g. Decky itself is broken)
type Workaround = { title: string; text: string; cmd?: string };

function workarounds(setup: Setup): Workaround[] {
  const c = setup.cli;
  const list: Workaround[] = [];
  if (setup.distro === "steamos") {
    list.push({
      title: "sudo asks for a password you never set",
      text: "SteamOS has no password by default. Set one once:",
      cmd: "passwd",
    });
  }
  list.push(
    { title: "Decky is missing or won't open", text: "Switch to Desktop Mode, open Konsole and run:", cmd: `sudo ${c} reinstall-decky` },
    { title: "A Decky update broke something", text: "Goes back to the Decky version you had before:", cmd: `sudo ${c} rollback-decky` },
    { title: "See the latest report without Decky", text: "In Konsole run the command below, or open ~/upkeep/latest.txt", cmd: `${c} show` },
    { title: "Update manually", text: "Same as Update now:", cmd: `sudo ${c} run --manual` },
    { title: "Check for updates manually", text: "Same as Check for updates (installs nothing):", cmd: `sudo ${c} check` },
  );
  if (setup.distro === "bazzite") {
    list.push(
      {
        title: "Game Mode update stuck at 100%",
        text: "Skip Steam's update button and use Update now, or run:",
        cmd: `sudo ${c} run --manual`,
      },
      {
        title: "A system update broke something",
        text: "Restart and pick the previous entry in the boot menu, or run this and restart:",
        cmd: "sudo rpm-ostree rollback",
      },
    );
  } else {
    list.push({
      title: "A system update broke something",
      text: "Restart and choose the previous version in the SteamOS boot menu. On Steam Deck, hold the ••• button while turning it on.",
    });
  }
  list.push(
    {
      title: "A plugin broke and wasn't fixed",
      text: "Backups are in ~/upkeep/backups/<date>/plugins/. Replace the broken folder with the backup:",
      cmd: "sudo rm -rf ~/homebrew/plugins/<name> && sudo cp -a ~/upkeep/backups/<date>/plugins/<name> ~/homebrew/plugins/ && sudo systemctl restart plugin_loader",
    },
    {
      title: "Turn off automatic updates without Decky",
      text: "Stops the schedule (turn back on with enable --now):",
      cmd: "sudo systemctl disable --now upkeep-run.timer",
    },
    { title: "Watch what upkeep is doing", text: "Shows the live log:", cmd: "journalctl -fu upkeep-run -u upkeep-manual" },
  );
  return list;
}

const WorkaroundsSection: FC<{ setup: Setup }> = ({ setup }) => (
  <PanelSection title="Workarounds">
    <Note text="Use these in Desktop Mode → Konsole when a button can't help." />
    {workarounds(setup).map((w, k) => (
      <PanelSectionRow key={k}>
        <Field
          focusable
          label={w.title}
          description={
            <div>
              <div>{w.text}</div>
              {w.cmd && <div style={CMD_STYLE}>{w.cmd}</div>}
            </div>
          }
        />
      </PanelSectionRow>
    ))}
  </PanelSection>
);

// "Think the new Decky update broke something?" -> its own page
const RollbackSection: FC<{ onOpen: () => void }> = ({ onOpen }) => (
  <PanelSection title="Decky problems">
    <PanelSectionRow>
      <Field
        focusable
        bottomSeparator="none"
        label="Think the new Decky update broke something?"
        description="You can go back to the Decky version you had before."
      />
    </PanelSectionRow>
    <PanelSectionRow>
      <ButtonItem layout="below" onClick={onOpen}>
        Roll back Decky
      </ButtonItem>
    </PanelSectionRow>
  </PanelSection>
);

const RollbackPage: FC<{ setup: Setup; running: Running; onStart: (k: Running) => void; onBack: () => void }> = ({
  setup,
  running,
  onStart,
  onBack,
}) => {
  // undefined = still looking, null = couldn't find out
  const [info, setInfo] = useState<RollbackInfo | null | undefined>(undefined);

  useEffect(() => {
    rollbackInfo()
      .then(setInfo)
      .catch((e) => {
        console.error("Upkeep", e);
        setInfo(null);
      });
  }, []);

  const target = info?.target ?? null;
  const cur = info?.current ?? "your current version";

  return (
    <PanelSection title="Roll back Decky">
      <PanelSectionRow>
        <Field
          focusable
          bottomSeparator="none"
          label="Think the new Decky update broke something?"
          description="If plugins stopped loading, or this menu started misbehaving right after Decky updated, Upkeep can put back the Decky version you had before."
        />
      </PanelSectionRow>
      {info === undefined && <Note text="Looking for an earlier version…" />}
      {info === null && <Note text="⚠️ Couldn't check. Is the Upkeep script installed?" />}
      {info && (
        <>
          <PanelSectionRow>
            <Field focusable bottomSeparator="none" label="Installed now">
              {info.current ?? "Unknown"}
            </Field>
          </PanelSectionRow>
          {info.held && (
            <Note text={`Upkeep is already holding Decky back from ${info.held} after an earlier rollback.`} />
          )}
          {target ? (
            <>
              <PanelSectionRow>
                <Field
                  focusable
                  bottomSeparator="none"
                  label="Goes back to"
                  description={
                    target.source === "backup"
                      ? `The copy Upkeep saved${target.saved ? ` on ${fmtTime(target.saved)}` : ""}`
                      : "Downloaded from Decky's own releases (no saved copy on this PC)"
                  }
                >
                  {target.version}
                </Field>
              </PanelSectionRow>
              <PanelSectionRow>
                <Field
                  focusable
                  bottomSeparator="none"
                  label="What happens"
                  description={
                    <div>
                      <div>1. Saves a copy of {cur}.</div>
                      <div>2. Puts {target.version} back and restarts Decky. This menu closes for about a minute.</div>
                      <div>
                        3. If {target.version} doesn't start, {cur} is restored.
                      </div>
                      <div>4. Upkeep then leaves Decky alone until a release newer than {cur} comes out.</div>
                      <div>Changed your mind later? Reinstall Decky puts the newest version back.</div>
                    </div>
                  }
                />
              </PanelSectionRow>
              <PanelSectionRow>
                <ButtonItem
                  layout="below"
                  disabled={running !== null}
                  onClick={async () => {
                    if (await rollbackDecky()) {
                      onStart("rollback");
                      toaster.toast({
                        title: "Upkeep",
                        body: `Rolling Decky back to ${target.version}. Back in about a minute.`,
                      });
                      onBack();
                    }
                  }}
                >
                  {`Roll back to ${target.version}`}
                </ButtonItem>
              </PanelSectionRow>
            </>
          ) : (
            <Note text="No earlier Decky version is available to go back to." />
          )}
          <PanelSectionRow>
            <Field
              focusable
              bottomSeparator="none"
              label="If Decky won't open at all"
              description={
                <div>
                  <div>Do the same thing from Desktop Mode → Konsole:</div>
                  <div style={CMD_STYLE}>{`sudo ${setup.cli} rollback-decky`}</div>
                </div>
              }
            />
          </PanelSectionRow>
        </>
      )}
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={onBack}>
          Back
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
};

// First-run setup (and "Change distro")
const SetupPage: FC<{ setup: Setup; changing: boolean; onDone: (s: Setup) => void; onCancel: () => void }> = ({
  setup,
  changing,
  onDone,
  onCancel,
}) => {
  const choose = async (d: Distro) => {
    const apply = async () => onDone(await setDistro(d));
    if (setup.detected && setup.detected !== d) {
      showModal(
        <ConfirmModal
          strTitle={`This doesn't look like ${DISTRO_NAME[d]}`}
          strDescription={`This PC looks like ${DISTRO_NAME[setup.detected]}. If you pick ${DISTRO_NAME[d]}, system updates will use the wrong commands and fail. Use ${DISTRO_NAME[d]} anyway?`}
          strOKButtonText={`Use ${DISTRO_NAME[d]}`}
          strCancelButtonText="Go back"
          onOK={apply}
        />,
      );
    } else {
      await apply();
    }
  };

  const option = (d: Distro) =>
    `${DISTRO_NAME[d]}${setup.detected === d ? " (detected)" : ""}${changing && setup.distro === d ? " · current" : ""}`;

  return (
    <PanelSection title={changing ? "Change distro" : "Welcome to Upkeep"}>
      {!changing && (
        <Note text="Keeps your system, Flatpaks, Decky and plugins updated, then checks that everything still works." />
      )}
      <PanelSectionRow>
        <Field
          focusable
          bottomSeparator="none"
          label="ℹ️ Made for Bazzite"
          description="Upkeep is designed specifically for Bazzite, and built to be compatible with SteamOS."
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <Field
          focusable
          bottomSeparator="none"
          label="Which system are you running?"
          description={
            setup.detected
              ? `Detected: ${DISTRO_NAME[setup.detected]}`
              : "Couldn't detect it automatically. Pick the one you installed."
          }
        />
      </PanelSectionRow>
      {(["bazzite", "steamos"] as Distro[]).map((d) => (
        <PanelSectionRow key={d}>
          <ButtonItem layout="below" onClick={() => choose(d)}>
            {option(d)}
          </ButtonItem>
        </PanelSectionRow>
      ))}
      <PanelSectionRow>
        <Field
          focusable
          bottomSeparator="none"
          label="What changes"
          description="System updates use rpm-ostree on Bazzite and steamos-update on SteamOS. Flatpaks, Decky, plugins and reports work the same on both."
        />
      </PanelSectionRow>
      {!setup.installed && (
        <PanelSectionRow>
          <Field
            focusable
            bottomSeparator="none"
            label="⚠️ Upkeep script not installed"
            description="In Desktop Mode, run ./install.sh from the bazzite-upkeep folder, then come back here."
          />
        </PanelSectionRow>
      )}
      {changing && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onCancel}>
            Cancel
          </ButtonItem>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
};

const ChangeDistroSection: FC<{ setup: Setup; onChange: () => void }> = ({ setup, onChange }) => (
  <PanelSection title="Setup">
    <Note text={`System: ${DISTRO_NAME[setup.distro]}`} />
    <PanelSectionRow>
      <ButtonItem layout="below" onClick={onChange}>
        Change distro
      </ButtonItem>
    </PanelSectionRow>
  </PanelSection>
);

// ---- main panel
const Content: FC = () => {
  const [report, setReport] = useState<Report | null | undefined>(undefined);
  const [check, setCheck] = useState<Report | null>(null);
  const [running, setRunning] = useState<Running>(null);
  const [allFlatpaks, setAllFlatpaks] = useState(false);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [changing, setChanging] = useState(false);
  const [rollback, setRollback] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);

  const refresh = async () => {
    try {
      setReport(await getReport());
      setCheck(await getCheck());
      setRunning(await isRunning());
    } catch (e) {
      console.error("Upkeep", e);
      setReport(null);
    }
  };

  useEffect(() => {
    getSetup()
      .then(setSetup)
      .catch((e) => console.error("Upkeep", e));
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (report) markSeen(reportKey(report), "report");
  }, [report?.generated, report?.health_checked]);

  // While an update runs, read its progress every second
  useEffect(() => {
    if (running !== "update") {
      setProgress(null);
      return;
    }
    let live = true;
    const tick = async () => {
      try {
        const p = await getProgress();
        if (live) setProgress(p);
      } catch (e) {
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
    return (
      <PanelSection>
        <Note text="Loading…" />
      </PanelSection>
    );
  }

  if (!setup.done || changing) {
    return (
      <SetupPage
        setup={setup}
        changing={changing}
        onDone={(s) => {
          setSetup(s);
          setChanging(false);
        }}
        onCancel={() => setChanging(false)}
      />
    );
  }

  if (rollback) {
    return <RollbackPage setup={setup} running={running} onStart={setRunning} onBack={() => setRollback(false)} />;
  }

  // Only show a check result if it's newer than the last update run
  const freshCheck = check && (!report || new Date(check.generated) > new Date(report.generated)) ? check : null;
  // Shown under the buttons: live progress during an update, otherwise the update check
  const live =
    running === "update" ? (
      <ProgressSection progress={progress} />
    ) : (
      freshCheck && <AvailableSection check={freshCheck} running={running} onStart={setRunning} />
    );

  if (report === null) {
    return (
      <>
        <PanelSection title="Upkeep">
          <PanelSectionRow>
            <Field focusable label="No report yet" description="Runs on your schedule, or update now." />
          </PanelSectionRow>
          {running === "rollback" && <Note text="↩️ Rolling Decky back…" />}
          <ActionButtons running={running} onStart={setRunning} />
        </PanelSection>
        {live}
        <RollbackSection onOpen={() => setRollback(true)} />
        <ScheduleSection />
        <ChangeDistroSection setup={setup} onChange={() => setChanging(true)} />
        <WorkaroundsSection setup={setup} />
      </>
    );
  }

  const n = report.issues.length;
  const changedPlugins = report.plugins.filter((p) => p.status !== "unchanged");
  const samePlugins = report.plugins.length - changedPlugins.length;
  const flatpaks = allFlatpaks ? report.flatpaks : report.flatpaks.slice(0, FLATPAK_PREVIEW);
  const hiddenFlatpaks = report.flatpaks.length - flatpaks.length;
  const rt = report.runtimes_updated ?? 0;

  return (
    <>
      <PanelSection title={fmtTime(report.generated)}>
        <PanelSectionRow>
          <Field
            focusable
            bottomSeparator="none"
            label={
              n === 0
                ? report.partial
                  ? "✅ Selected updates installed and working"
                  : "✅ Everything updated and working"
                : `⚠️ ${n} issue${n > 1 ? "s need" : " needs"} a look`
            }
          />
        </PanelSectionRow>
        {running === "rollback" && <Note text="↩️ Rolling Decky back…" />}
        <ActionButtons running={running} onStart={setRunning} />
      </PanelSection>

      {live}

      {n > 0 && (
        <PanelSection title="Issues">
          {report.issues.map((i, k) => (
            <IssueItem key={k} issue={i} />
          ))}
        </PanelSection>
      )}

      <PanelSection title="System">
        {report.system.map((r, k) => (
          <RowItem key={k} row={r} />
        ))}
      </PanelSection>

      <PanelSection title="Decky Plugins">
        {changedPlugins.map((r, k) => (
          <RowItem key={k} row={r} />
        ))}
        {samePlugins > 0 && (
          <Note
            text={`${changedPlugins.length === 0 && samePlugins > 1 ? "All " : ""}${samePlugins} plugin${samePlugins !== 1 ? "s" : ""} already up to date`}
          />
        )}
        {report.plugins.length === 0 && <Note text="No plugins installed" />}
      </PanelSection>

      <PanelSection title="Flatpaks">
        {flatpaks.map((r, k) => (
          <RowItem key={k} row={r} />
        ))}
        {report.flatpaks.length === 0 && <Note text="No app updates" />}
        {hiddenFlatpaks > 0 && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => setAllFlatpaks(true)}>
              {`Show ${hiddenFlatpaks} more`}
            </ButtonItem>
          </PanelSectionRow>
        )}
        {rt > 0 && <Note text={`+ ${rt} system runtime${rt !== 1 ? "s" : ""} updated`} />}
      </PanelSection>

      {report.health.length > 0 && (
        <PanelSection title="Health Check">
          {report.health.map((h, k) => (
            <Note key={k} text={`${h.ok ? "✅" : "⚠️"} ${h.text}`} />
          ))}
          {report.health_checked && <Note text={`Checked ${fmtTime(report.health_checked)}`} />}
        </PanelSection>
      )}

      <RollbackSection onOpen={() => setRollback(true)} />
      <ScheduleSection />
      <ChangeDistroSection setup={setup} onChange={() => setChanging(true)} />
      <WorkaroundsSection setup={setup} />
    </>
  );
};

export default definePlugin(() => {
  // After a reinstall, Decky reloads: say how it went (once, if recent)
  (async () => {
    try {
      const a = await getAction();
      if (!a || Date.now() - new Date(a.time).getTime() > 15 * 60 * 1000) return;
      if (await wasSeen(a.time, "action")) return;
      await markSeen(a.time, "action");
      toaster.toast({ title: "Upkeep", body: `${a.ok ? "✅" : "⚠️"} ${a.message}` });
    } catch (e) {
      console.error("Upkeep", e);
    }
  })();

  // Pop a toast once per report if something needs attention
  (async () => {
    try {
      const r = await getReport();
      if (!r || r.issues.length === 0) return;
      if (await wasSeen(reportKey(r), "report")) return;
      const n = r.issues.length;
      toaster.toast({
        title: "Upkeep",
        body: `⚠️ ${n} issue${n > 1 ? "s" : ""}: open Upkeep for details`,
      });
    } catch (e) {
      console.error("Upkeep", e);
    }
  })();

  return {
    name: "Upkeep",
    titleView: <div className={staticClasses.Title}>Upkeep</div>,
    content: <Content />,
    icon: <FaClipboardCheck />,
    onDismount() {},
  };
});
