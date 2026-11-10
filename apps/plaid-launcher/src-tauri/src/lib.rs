//! Plaid launcher backend: library scan, box art, native recompilation through
//! `scripts/native.py`, launching builds and per-game settings.

mod covers;
mod progress;
mod rom;

use base64::Engine as _;
use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::sync::mpsc;
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase", default)]
struct Config {
    rom_dir: Option<String>,
    plaid_root: String,
    /// Length of native.py's acceptance run after each build.
    validation_seconds: u32,
}

impl Default for Config {
    fn default() -> Self {
        // the checkout this launcher was built from: <root>/apps/plaid-launcher/src-tauri
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(3)
            .unwrap_or(Path::new("."));
        Config {
            rom_dir: None,
            plaid_root: root.display().to_string(),
            validation_seconds: 10,
        }
    }
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct Game {
    id: String,
    title: String,
    file_name: String,
    path: String,
    internal_name: String,
    game_code: String,
    region: String,
    version: u8,
    byte_order: &'static str,
    size_mb: f32,
    compiled: bool,
    native_complete: Option<bool>,
    residual_sites: Option<usize>,
    save_dir: String,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase", tag = "kind")]
enum CompileEvent {
    Progress {
        id: String,
        progress: progress::Progress,
    },
    Log {
        id: String,
        line: String,
    },
    Done {
        id: String,
    },
    Failed {
        id: String,
        message: String,
    },
    Cancelled {
        id: String,
    },
}

#[derive(Default)]
struct Running {
    id: Option<String>,
    pid: Option<u32>,
    cancelled: bool,
}

type Shared = Mutex<Running>;

fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}

fn config_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_config_dir().map_err(err)?;
    std::fs::create_dir_all(&dir).map_err(err)?;
    Ok(dir)
}

fn hidden(cmd: &mut Command) -> &mut Command {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd
}

#[tauri::command]
fn get_config(app: AppHandle) -> Result<Config, String> {
    let file = config_dir(&app)?.join("config.json");
    Ok(std::fs::read(file)
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or_default())
}

#[tauri::command]
fn set_config(app: AppHandle, config: Config) -> Result<(), String> {
    if !Path::new(&config.plaid_root)
        .join("scripts/native.py")
        .exists()
    {
        return Err(format!(
            "{} is not a Plaid checkout (scripts/native.py is missing)",
            config.plaid_root
        ));
    }
    std::fs::write(
        config_dir(&app)?.join("config.json"),
        serde_json::to_vec_pretty(&config).map_err(err)?,
    )
    .map_err(err)
}

fn rom_files(dir: &Path, depth: u32, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() && depth > 0 {
            rom_files(&path, depth - 1, out);
        } else if path
            .extension()
            .and_then(|e| e.to_str())
            .is_some_and(|e| ["z64", "v64", "n64"].contains(&e.to_ascii_lowercase().as_str()))
        {
            out.push(path);
        }
    }
}

fn library(config: &Config) -> Vec<Game> {
    let Some(dir) = &config.rom_dir else {
        return vec![];
    };
    let mut files = vec![];
    rom_files(Path::new(dir), 2, &mut files);
    let root = Path::new(&config.plaid_root);
    let mut games: Vec<Game> = files
        .iter()
        .filter_map(|path| {
            let (order, header) = rom::probe(path)?;
            let stem = path.file_stem()?.to_string_lossy().to_string();
            let id = rom::native_name(&stem);
            let out = root.join("target/native").join(&id);
            let manifest: Option<serde_json::Value> =
                std::fs::read(out.join("native-manifest.json"))
                    .ok()
                    .and_then(|b| serde_json::from_slice(&b).ok());
            Some(Game {
                title: rom::display_title(&stem),
                file_name: path.file_name()?.to_string_lossy().to_string(),
                path: path.display().to_string(),
                internal_name: header.internal_name,
                game_code: header.game_code,
                region: header.region.to_string(),
                version: header.version,
                byte_order: match order {
                    rom::Order::Z64 => "z64",
                    rom::Order::V64 => "v64",
                    rom::Order::N64 => "n64",
                },
                size_mb: std::fs::metadata(path)
                    .map(|m| m.len() as f32 / 1048576.0)
                    .unwrap_or(0.0),
                compiled: root
                    .join(format!("target/rt64-shim/Release/{id}-rt64.exe"))
                    .exists(),
                native_complete: manifest
                    .as_ref()
                    .and_then(|m| m["native_complete"].as_bool()),
                residual_sites: manifest
                    .as_ref()
                    .and_then(|m| m["residual_sites"].as_array().map(Vec::len)),
                save_dir: out.display().to_string(),
                id,
            })
        })
        .collect();
    games.sort_by_key(|g| g.title.to_lowercase());
    games.dedup_by(|a, b| a.id == b.id);
    games
}

#[tauri::command]
fn scan_library(app: AppHandle) -> Result<Vec<Game>, String> {
    Ok(library(&get_config(app)?))
}

fn find(app: &AppHandle, id: &str) -> Result<(Config, Game), String> {
    let config = get_config(app.clone())?;
    let game = library(&config)
        .into_iter()
        .find(|g| g.id == id)
        .ok_or_else(|| format!("{id} is no longer in the ROM folder"))?;
    Ok((config, game))
}

#[tauri::command]
async fn get_cover(app: AppHandle, id: String) -> Result<String, String> {
    let (_, game) = find(&app, &id)?;
    let cache = config_dir(&app)?.join("covers");
    tauri::async_runtime::spawn_blocking(move || {
        let stem = Path::new(&game.file_name)
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        let file = covers::cover(&cache, &game.id, &stem, &game.internal_name, &game.region)?;
        let bytes = std::fs::read(file).map_err(err)?;
        Ok(format!(
            "data:image/png;base64,{}",
            base64::engine::general_purpose::STANDARD.encode(bytes)
        ))
    })
    .await
    .map_err(err)?
}

/// The ROM in big-endian order: the file itself, or a converted copy in app data.
fn z64_path(app: &AppHandle, game: &Game) -> Result<PathBuf, String> {
    let path = PathBuf::from(&game.path);
    let order = rom::probe(&path).ok_or("not an N64 ROM")?.0;
    if order == rom::Order::Z64 {
        return Ok(path);
    }
    let dir = config_dir(app)?.join("roms");
    std::fs::create_dir_all(&dir).map_err(err)?;
    let copy = dir.join(format!(
        "{}.z64",
        path.file_stem().unwrap_or_default().to_string_lossy()
    ));
    if !copy.exists() {
        let mut bytes = std::fs::read(&path).map_err(err)?;
        rom::to_z64(&mut bytes, order);
        std::fs::write(&copy, bytes).map_err(err)?;
    }
    Ok(copy)
}

fn count_c_files(dir: &Path) -> u32 {
    std::fs::read_dir(dir)
        .map(|entries| {
            entries
                .flatten()
                .map(|e| {
                    let p = e.path();
                    if p.is_dir() {
                        count_c_files(&p)
                    } else {
                        u32::from(p.extension().is_some_and(|x| x == "c"))
                    }
                })
                .sum()
        })
        .unwrap_or(0)
}

/// Runs one build step, streaming its output into progress events and the build log.
/// Returns its exit status, or None when it could not start.
fn run_step(
    app: &AppHandle,
    id: &str,
    mut cmd: Command,
    tracker: &mut progress::Tracker,
    log: &mut Option<std::fs::File>,
    tail: &mut Vec<String>,
    on_line: &mut dyn FnMut(&mut progress::Tracker),
) -> Result<std::process::ExitStatus, String> {
    use std::io::Write as _;
    let emit = |e: CompileEvent| drop(app.emit("compile", e));
    cmd.stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null());
    let mut child = hidden(&mut cmd)
        .spawn()
        .map_err(|e| format!("could not start {:?}: {e}", cmd.get_program()))?;
    app.state::<Shared>().lock().unwrap().pid = Some(child.id());
    let (tx, rx) = mpsc::channel::<String>();
    for stream in [
        Box::new(child.stdout.take().unwrap()) as Box<dyn std::io::Read + Send>,
        Box::new(child.stderr.take().unwrap()),
    ] {
        let tx = tx.clone();
        std::thread::spawn(move || {
            BufReader::new(stream)
                .lines()
                .map_while(Result::ok)
                .for_each(|l| drop(tx.send(l)))
        });
    }
    drop(tx);
    for line in rx {
        if let Some(f) = log.as_mut() {
            let _ = writeln!(f, "{line}");
        }
        if tracker.line(&line).is_some() {
            on_line(tracker);
            emit(CompileEvent::Progress {
                id: id.to_string(),
                progress: tracker.progress(),
            });
        }
        tail.push(line.clone());
        if tail.len() > 40 {
            tail.remove(0);
        }
        emit(CompileEvent::Log {
            id: id.to_string(),
            line,
        });
    }
    child.wait().map_err(err)
}

#[tauri::command]
fn compile_game(app: AppHandle, running: State<'_, Shared>, id: String) -> Result<(), String> {
    let (config, game) = find(&app, &id)?;
    let rom = z64_path(&app, &game)?;
    let root = PathBuf::from(&config.plaid_root);
    {
        let mut r = running.lock().unwrap();
        if let Some(busy) = &r.id {
            return Err(format!(
                "{busy} is already compiling; one game builds at a time"
            ));
        }
        *r = Running {
            id: Some(id.clone()),
            ..Default::default()
        };
    }
    let cargo_bin = std::env::var("USERPROFILE")
        .map(|h| format!(r"{h}\.cargo\bin;"))
        .unwrap_or_default();
    let path = format!("{cargo_bin}{}", std::env::var("PATH").unwrap_or_default());
    std::thread::spawn(move || {
        let emit = |e: CompileEvent| drop(app.emit("compile", e));
        let out = root.join("target/native").join(&id);
        let _ = std::fs::create_dir_all(&out);
        // the full output, for diagnosing a build after the window is gone
        let mut log = std::fs::File::create(out.join("launcher-build.log")).ok();
        let crates = std::fs::read_to_string(root.join("Cargo.lock"))
            .map(|l| l.matches("[[package]]").count() as u32)
            .unwrap_or(0);
        let mut tracker = progress::Tracker::new(crates);
        let mut tail = vec![];
        emit(CompileEvent::Progress {
            id: id.clone(),
            progress: tracker.progress(),
        });

        // Build the recompiler first, visibly: native.py builds it quietly, which looked like a hang.
        let mut cargo = Command::new("cargo");
        cargo
            .args(["build", "--release", "-p", "plaid", "--color", "never"])
            .current_dir(&root)
            .env("PATH", &path);
        let built = run_step(
            &app,
            &id,
            cargo,
            &mut tracker,
            &mut log,
            &mut tail,
            &mut |_| {},
        );
        let status = match built {
            Ok(s) if s.success() => {
                let mut py = Command::new("python");
                py.args(["-u", "scripts/native.py"])
                    .arg(&rom)
                    .args([
                        "--rt64",
                        "--seconds",
                        &config.validation_seconds.to_string(),
                    ])
                    .current_dir(&root)
                    .env("PATH", &path)
                    .env("PYTHONUNBUFFERED", "1")
                    .env("SDL_AUDIODRIVER", "dummy");
                let out = out.clone();
                run_step(&app, &id, py, &mut tracker, &mut log, &mut tail, &mut |t| {
                    if t.in_gcc() && t.expected == 0 {
                        t.expected = count_c_files(&out).max(1);
                    }
                })
                .map(|s| (s, "native.py"))
            }
            other => other.map(|s| (s, "cargo build")),
        };
        let cancelled = std::mem::take(&mut *app.state::<Shared>().lock().unwrap()).cancelled;
        emit(match status {
            _ if cancelled => CompileEvent::Cancelled { id },
            Ok((s, _)) if s.success() => CompileEvent::Done { id },
            Ok((s, step)) => CompileEvent::Failed {
                id,
                message: format!("{step} exited with {s}\n{}", tail.join("\n")),
            },
            Err(e) => CompileEvent::Failed { id, message: e },
        });
    });
    Ok(())
}

#[tauri::command]
fn cancel_compile(running: State<'_, Shared>) -> Result<(), String> {
    let mut r = running.lock().unwrap();
    let pid = r.pid.ok_or("nothing is compiling")?;
    r.cancelled = true;
    // the whole tree: python, plaid and the gcc workers
    hidden(Command::new("taskkill").args(["/PID", &pid.to_string(), "/T", "/F"]))
        .status()
        .map_err(err)?;
    Ok(())
}

#[tauri::command]
fn play_game(app: AppHandle, id: String) -> Result<(), String> {
    let (config, game) = find(&app, &id)?;
    let root = PathBuf::from(&config.plaid_root);
    let exe = root.join(format!("target/rt64-shim/Release/{id}-rt64.exe"));
    if !exe.exists() {
        return Err("compile this game first".into());
    }
    let rom = z64_path(&app, &game)?;
    let out = PathBuf::from(&game.save_dir);
    // shortcut: launcher settings are stored but not yet read by the runtime (keyboard map, 4:3); pass them once it accepts a config
    Command::new(exe)
        .arg("--rom")
        .arg(rom)
        .arg("--sram")
        .arg(out.join(format!("{id}.sra")))
        .arg("--flash")
        .arg(out.join(format!("{id}.fla")))
        .arg("--save")
        .arg(out.join(format!("{id}.eep")))
        .args(["--stop-at", "none"])
        .current_dir(&root)
        .spawn()
        .map_err(err)?;
    Ok(())
}

fn settings_file(app: &AppHandle, id: &str) -> Result<PathBuf, String> {
    let dir = config_dir(app)?.join("games");
    std::fs::create_dir_all(&dir).map_err(err)?;
    Ok(dir.join(format!("{}.json", rom::native_name(id))))
}

#[tauri::command]
fn get_settings(app: AppHandle, id: String) -> Result<serde_json::Value, String> {
    Ok(std::fs::read(settings_file(&app, &id)?)
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or(serde_json::Value::Null))
}

#[tauri::command]
fn set_settings(app: AppHandle, id: String, settings: serde_json::Value) -> Result<(), String> {
    std::fs::write(
        settings_file(&app, &id)?,
        serde_json::to_vec_pretty(&settings).map_err(err)?,
    )
    .map_err(err)
}

#[derive(Serialize)]
struct SaveFile {
    name: String,
    kind: &'static str,
    bytes: u64,
}

#[tauri::command]
fn list_saves(app: AppHandle, id: String) -> Result<Vec<SaveFile>, String> {
    let (_, game) = find(&app, &id)?;
    let Ok(entries) = std::fs::read_dir(&game.save_dir) else {
        return Ok(vec![]);
    };
    Ok(entries
        .flatten()
        .filter_map(|e| {
            let kind = match e.path().extension()?.to_str()? {
                "eep" => "EEPROM",
                "sra" => "SRAM",
                "fla" => "FlashRAM",
                "mpk" => "Controller Pak",
                _ => return None,
            };
            Some(SaveFile {
                name: e.file_name().to_string_lossy().to_string(),
                kind,
                bytes: e.metadata().ok()?.len(),
            })
        })
        .collect())
}

#[tauri::command]
fn open_folder(path: String) -> Result<(), String> {
    std::fs::create_dir_all(&path).map_err(err)?;
    Command::new(if cfg!(windows) {
        "explorer"
    } else {
        "xdg-open"
    })
    .arg(path)
    .spawn()
    .map_err(err)?;
    Ok(())
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct UpdateInfo {
    current: String,
    behind: u32,
}

#[tauri::command]
async fn check_updates(app: AppHandle) -> Result<UpdateInfo, String> {
    let root = get_config(app)?.plaid_root;
    tauri::async_runtime::spawn_blocking(move || {
        let git = |args: &[&str]| -> Result<String, String> {
            let out = hidden(Command::new("git").arg("-C").arg(&root).args(args))
                .output()
                .map_err(err)?;
            if !out.status.success() {
                return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());
            }
            Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
        };
        git(&["fetch", "--quiet", "origin", "main"])?;
        Ok(UpdateInfo {
            current: git(&["rev-parse", "--short", "HEAD"])?,
            behind: git(&["rev-list", "--count", "HEAD..origin/main"])?
                .parse()
                .unwrap_or(0),
        })
    })
    .await
    .map_err(err)?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Shared::default())
        .invoke_handler(tauri::generate_handler![
            get_config,
            set_config,
            scan_library,
            get_cover,
            compile_game,
            cancel_compile,
            play_game,
            get_settings,
            set_settings,
            list_saves,
            open_folder,
            check_updates
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
