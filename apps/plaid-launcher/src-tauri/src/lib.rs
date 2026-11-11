//! Plaid launcher backend: library scan, box art, native recompilation through
//! `scripts/native.py`, launching builds and per-game settings.

mod covers;
mod discord;
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
            validation_seconds: 30,
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

/// Where the recompiler runs from and where its outputs go.
struct Engine {
    /// the engine bundle installed with the app, or a Plaid checkout
    root: PathBuf,
    /// holds target/native/<id> and target/rt64-shim/Release/<id>-rt64.exe
    work: PathBuf,
    bundled: bool,
}

/// The engine bundle (ADR-0316) a release build runs, pinned by release.py at build time.
/// Dev builds have none and run the configured checkout in place.
const ENGINE_URL: Option<&str> = option_env!("PLAID_ENGINE_URL");
const ENGINE_SHA256: Option<&str> = option_env!("PLAID_ENGINE_SHA256");

/// A release app runs its pinned engine from its data folder, downloaded on first run, and
/// keeps builds beside it; it is "bundled" from install on, even before the download.
fn engine(app: &AppHandle, config: &Config) -> Engine {
    match (ENGINE_SHA256, app.path().app_local_data_dir()) {
        (Some(sha), Ok(data)) => Engine {
            root: data.join("engine").join(&sha[..12]),
            work: data.join("work"),
            bundled: true,
        },
        _ => Engine {
            root: PathBuf::from(&config.plaid_root),
            work: PathBuf::from(&config.plaid_root),
            bundled: false,
        },
    }
}

#[tauri::command]
fn engine_bundled(app: AppHandle) -> Result<bool, String> {
    Ok(engine(&app, &get_config(app.clone())?).bundled)
}

/// True once the engine can run: always for a checkout, after the download for a release.
#[tauri::command]
fn engine_ready(app: AppHandle) -> Result<bool, String> {
    let e = engine(&app, &get_config(app.clone())?);
    Ok(!e.bundled || e.root.join("engine.json").exists())
}

#[derive(Serialize, Clone)]
struct EngineProgress {
    done: u64,
    total: u64,
    /// "download", then "unpack" (no byte progress)
    phase: &'static str,
}

static ENGINE_INSTALL: Mutex<()> = Mutex::new(());

/// Downloads the pinned engine zip, checks its SHA-256, unpacks it and drops older engines.
/// Emits `engine` progress events while downloading.
#[tauri::command]
async fn install_engine(app: AppHandle) -> Result<(), String> {
    let (Some(url), Some(sha)) = (ENGINE_URL, ENGINE_SHA256) else {
        return Ok(());
    };
    let root = engine(&app, &get_config(app.clone())?).root;
    tauri::async_runtime::spawn_blocking(move || {
        use sha2::Digest as _;
        use std::io::{Read as _, Write as _};
        // a second caller waits for the first download instead of starting its own
        let _one = ENGINE_INSTALL.lock().unwrap_or_else(|e| e.into_inner());
        if root.join("engine.json").exists() {
            return Ok(());
        }
        let dir = root.parent().ok_or("bad engine folder")?.to_path_buf();
        std::fs::create_dir_all(&dir).map_err(err)?;
        let part = dir.join(format!("{}.zip.part", &sha[..12]));
        let response = ureq::AgentBuilder::new()
            .timeout_read(std::time::Duration::from_secs(60))
            .build()
            .get(url)
            .call()
            .map_err(|e| format!("could not download the recompiler: {e}"))?;
        let total = response
            .header("Content-Length")
            .and_then(|l| l.parse().ok())
            .unwrap_or(0);
        let mut reader = response.into_reader();
        let mut file = std::fs::File::create(&part).map_err(err)?;
        let mut hash = sha2::Sha256::new();
        let (mut done, mut shown, mut buf) = (0u64, 0u64, vec![0u8; 1 << 16]);
        loop {
            let n = reader
                .read(&mut buf)
                .map_err(|e| format!("the download stopped: {e}"))?;
            if n == 0 {
                break;
            }
            hash.update(&buf[..n]);
            file.write_all(&buf[..n]).map_err(err)?;
            done += n as u64;
            if done - shown >= 1 << 20 {
                shown = done;
                let _ = app.emit("engine", EngineProgress { done, total, phase: "download" });
            }
        }
        drop(file);
        let got: String = hash.finalize().iter().map(|b| format!("{b:02x}")).collect();
        if !got.eq_ignore_ascii_case(sha) {
            let _ = std::fs::remove_file(&part);
            return Err("the downloaded recompiler is damaged (checksum mismatch); try again".into());
        }
        let _ = app.emit("engine", EngineProgress { done, total: done, phase: "unpack" });
        // unpack beside the final folder, then rename, so a half-unpacked engine never counts as ready
        let tmp = dir.join(format!("{}.tmp", &sha[..12]));
        let _ = std::fs::remove_dir_all(&tmp);
        zip::ZipArchive::new(std::fs::File::open(&part).map_err(err)?)
            .and_then(|mut z| z.extract(&tmp))
            .map_err(|e| format!("could not unpack the recompiler: {e}"))?;
        let _ = std::fs::remove_dir_all(&root);
        std::fs::rename(tmp.join("engine"), &root).map_err(err)?;
        let _ = std::fs::remove_dir_all(&tmp);
        let _ = std::fs::remove_file(&part);
        // older engines; one still in use stays until the next start
        for old in std::fs::read_dir(&dir).map_err(err)?.flatten() {
            if old.path() != root {
                let _ = std::fs::remove_dir_all(old.path()).or_else(|_| std::fs::remove_file(old.path()));
            }
        }
        Ok(())
    })
    .await
    .map_err(err)?
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
    if !engine(&app, &config).bundled
        && !Path::new(&config.plaid_root)
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

fn library(app: &AppHandle, config: &Config) -> Vec<Game> {
    let Some(dir) = &config.rom_dir else {
        return vec![];
    };
    let mut files = vec![];
    rom_files(Path::new(dir), 2, &mut files);
    let root = engine(app, config).work;
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
    Ok(library(&app, &get_config(app.clone())?))
}

fn find(app: &AppHandle, id: &str) -> Result<(Config, Game), String> {
    let config = get_config(app.clone())?;
    let game = library(app, &config)
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

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct GameInfo {
    title: String,
    description: Option<String>,
    extract: String,
    url: String,
}

/// True when `text` names a year after the N64's lifetime (a remake's "2026 video game").
fn late_year(text: &str) -> bool {
    text.as_bytes()
        .windows(4)
        .filter_map(|w| std::str::from_utf8(w).ok()?.parse::<u32>().ok())
        .any(|y| (2003..2100).contains(&y))
}

#[test]
fn late_year_spots_remakes() {
    assert!(late_year("2026 video game"));
    assert!(!late_year("2000 video game"));
    assert!(!late_year("1998 video game"));
}

/// A short "about" for the game page: the Wikipedia summary of the best search hit, cached.
#[tauri::command]
async fn game_info(app: AppHandle, id: String) -> Result<GameInfo, String> {
    let (_, game) = find(&app, &id)?;
    // info2: the first lookup could cache a remake's article
    let dir = config_dir(&app)?.join("info2");
    let file = dir.join(format!("{id}.json"));
    if let Some(info) = std::fs::read(&file)
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
    {
        return Ok(info);
    }
    tauri::async_runtime::spawn_blocking(move || {
        let json = |url: &str| -> Result<serde_json::Value, String> {
            serde_json::from_str(&covers::get(url)?.into_string().map_err(err)?).map_err(err)
        };
        let summary = |title: &str| {
            json(&format!(
                "https://en.wikipedia.org/api/rest_v1/page/summary/{}",
                covers::encode(&title.replace(' ', "_"))
            ))
        };
        // the N64 game's own article: it names the console and is not a remake or remaster
        let n64 = |p: &serde_json::Value| {
            let description = p["description"].as_str().unwrap_or("");
            p["type"] == "standard"
                && p["extract"].as_str().unwrap_or("").contains("Nintendo 64")
                && !late_year(description)
        };
        // exact title first ("Zelda - Ocarina of Time" is "Zelda: Ocarina of Time"), then search hits
        let mut candidates = vec![game.title.replace(" - ", ": ")];
        let query = format!("{} Nintendo 64 video game", game.title.replace(" - ", " "));
        let search = json(&format!(
            "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch={}",
            covers::encode(&query)
        ))?;
        candidates.extend(search["query"]["search"].as_array().into_iter().flatten()
            .filter_map(|h| h["title"].as_str().map(str::to_string)));
        let pages: Vec<(String, serde_json::Value)> = candidates
            .iter()
            .filter_map(|t| summary(t).ok().filter(|p| n64(p)).map(|p| (t.clone(), p)))
            .collect();
        // the game's own article ("1998 video game") over a series or franchise page
        let game_page = |p: &serde_json::Value| p["description"].as_str().is_some_and(|d| d.contains("video game") && !d.contains("series"));
        let (title, page) = pages
            .iter()
            .find(|(_, p)| game_page(p))
            .or(pages.first())
            .cloned()
            .ok_or("no article found")?;
        let info = GameInfo {
            title,
            description: page["description"].as_str().map(str::to_string),
            extract: page["extract"].as_str().unwrap_or_default().to_string(),
            url: page["content_urls"]["desktop"]["page"].as_str().unwrap_or_default().to_string(),
        };
        std::fs::create_dir_all(&dir).map_err(err)?;
        std::fs::write(&file, serde_json::to_vec(&info).map_err(err)?).map_err(err)?;
        Ok(info)
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
    let Engine {
        root,
        work,
        bundled,
    } = engine(&app, &config);
    if bundled && !root.join("engine.json").exists() {
        return Err("the recompiler is still downloading; compile when it finishes".into());
    }
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
        let out = work.join("target/native").join(&id);
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

        // A checkout builds the recompiler first, visibly: native.py builds it quietly, which
        // looked like a hang. The bundle ships it prebuilt.
        let built = if bundled {
            Ok(std::process::ExitStatus::default())
        } else {
            let mut cargo = Command::new("cargo");
            cargo
                .args(["build", "--release", "-p", "plaid", "--color", "never"])
                .current_dir(&root)
                .env("PATH", &path);
            run_step(
                &app,
                &id,
                cargo,
                &mut tracker,
                &mut log,
                &mut tail,
                &mut |_| {},
            )
        };
        let status = match built {
            Ok(s) if s.success() => {
                let mut py = if bundled {
                    // the bundle sets its own PATH, caches and temp dirs under PLAID_WORK_DIR
                    let mut c = Command::new(root.join(r"python\python.exe"));
                    c.args(["-B", "-u", "scripts/native.py"])
                        .env("PLAID_WORK_DIR", &work);
                    c
                } else {
                    let mut c = Command::new("python");
                    c.args(["-u", "scripts/native.py"]).env("PATH", &path);
                    c
                };
                py.arg(&rom)
                    .args([
                        "--rt64",
                        "--seconds",
                        &config.validation_seconds.to_string(),
                    ])
                    .current_dir(&root)
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
    let root = engine(&app, &config).work;
    let exe = root.join(format!("target/rt64-shim/Release/{id}-rt64.exe"));
    if !exe.exists() {
        return Err("compile this game first".into());
    }
    let rom = z64_path(&app, &game)?;
    let out = PathBuf::from(&game.save_dir);
    // The game's own settings, or the global defaults when it uses them; the runtime reads this file.
    let read = |id: &str| -> Option<serde_json::Value> {
        serde_json::from_slice(&std::fs::read(settings_file(&app, id).ok()?).ok()?).ok()
    };
    let settings = read(&id)
        .filter(|s| s["useDefaults"] == false)
        .or_else(|| read("defaults"))
        .unwrap_or(serde_json::Value::Null);
    let settings_path = out.join("launcher-settings.json");
    std::fs::create_dir_all(&out).map_err(err)?;
    std::fs::write(&settings_path, settings.to_string()).map_err(err)?;
    let base: Vec<std::ffi::OsString> = vec![
        "--rom".into(),
        rom.into(),
        "--sram".into(),
        out.join(format!("{id}.sra")).into(),
        "--flash".into(),
        out.join(format!("{id}.fla")).into(),
        "--save".into(),
        out.join(format!("{id}.eep")).into(),
        "--stop-at".into(),
        "none".into(),
    ];
    let mut extra: Vec<std::ffi::OsString> = vec![
        "--title".into(),
        game.title.clone().into(),
        "--config".into(),
        settings_path.into(),
    ];
    // fullscreen unless the player turned it off
    if settings["fullscreen"] != false {
        extra.push("--fullscreen".into());
    }
    // no console window behind the game
    let spawn = move |args: &[std::ffi::OsString]| {
        hidden(Command::new(&exe).args(args).current_dir(&root))
            .spawn()
            .map_err(err)
    };
    let mut child = spawn(&[base.clone(), extra].concat())?;
    let title = game.title.clone();
    std::thread::spawn(move || {
        // shortcut: a game compiled before the runtime knew --title/--config/--fullscreen
        // exits 2 at once on them; rerun it without them. Drop once every build is newer.
        let started = std::time::Instant::now();
        let mut fell_back = false;
        while started.elapsed() < std::time::Duration::from_secs(2) {
            match child.try_wait() {
                Ok(Some(s)) if s.code() == Some(2) && !fell_back => match spawn(&base) {
                    Ok(c) => {
                        child = c;
                        fell_back = true;
                    }
                    Err(_) => return,
                },
                Ok(None) => std::thread::sleep(std::time::Duration::from_millis(50)),
                _ => break,
            }
        }
        let presence = discord::playing(&title);
        let _ = child.wait();
        drop(presence);
    });
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
    /// What an update would bring in, newest first (merge and README-only commits left out).
    changes: Vec<Change>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct Change {
    sha: String,
    subject: String,
    when: String,
}

#[tauri::command]
async fn check_updates(app: AppHandle) -> Result<UpdateInfo, String> {
    let config = get_config(app.clone())?;
    if engine(&app, &config).bundled {
        // the engine ships inside app releases, which the app updater checks
        return Ok(UpdateInfo {
            current: app.package_info().version.to_string(),
            behind: 0,
            changes: vec![],
        });
    }
    let root = config.plaid_root;
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
            changes: git(&[
                "log",
                "--no-merges",
                "--format=%h%x1f%s%x1f%cr",
                "HEAD..origin/main",
            ])?
            .lines()
            .filter_map(|l| {
                let mut f = l.split('\u{1f}');
                Some(Change {
                    sha: f.next()?.into(),
                    subject: f.next()?.into(),
                    when: f.next()?.into(),
                })
            })
            .filter(|c| {
                !c.subject.starts_with("Update README") && !c.subject.starts_with("Add ADR-")
            })
            .collect(),
        })
    })
    .await
    .map_err(err)?
}

/// Merges the latest Plaid main into the compiler checkout; the recompiler
/// rebuilds itself on the next compile. (The app updates itself from releases.)
#[tauri::command]
async fn update_plaid(app: AppHandle, running: State<'_, Shared>) -> Result<(), String> {
    if let Some(busy) = &running.lock().unwrap().id {
        return Err(format!("{busy} is compiling; update after it finishes"));
    }
    let config = get_config(app.clone())?;
    if engine(&app, &config).bundled {
        return Err("this install updates its engine with the app".into());
    }
    let root = config.plaid_root;
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
        if !git(&["status", "--porcelain", "--untracked-files=no"])?.is_empty() {
            return Err(format!("{root} has uncommitted changes; update it by hand"));
        }
        git(&["fetch", "--quiet", "origin", "main"])?;
        if let Err(e) = git(&["merge", "--no-edit", "origin/main"]) {
            let _ = git(&["merge", "--abort"]);
            return Err(format!("the update does not merge cleanly: {e}"));
        }
        Ok(())
    })
    .await
    .map_err(err)?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(Shared::default())
        .invoke_handler(tauri::generate_handler![
            get_config,
            engine_bundled,
            engine_ready,
            install_engine,
            set_config,
            scan_library,
            get_cover,
            game_info,
            compile_game,
            cancel_compile,
            play_game,
            get_settings,
            set_settings,
            list_saves,
            open_folder,
            check_updates,
            update_plaid
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
