// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod detector;
mod macos_scanner;
mod windows_scanner;

use detector::{DetectedMeeting, DetectorEngine, MeetingCooldownTracker, WindowInfo};
use std::sync::Arc;
use std::time::Duration;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_notification::NotificationExt;

fn get_windows() -> Vec<WindowInfo> {
    #[cfg(target_os = "windows")]
    {
        windows_scanner::list_visible_windows()
    }
    #[cfg(target_os = "macos")]
    {
        macos_scanner::list_visible_windows()
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        Vec::new()
    }
}

#[tauri::command]
fn get_active_meeting() -> Option<DetectedMeeting> {
    let engine = DetectorEngine::new();
    let windows = get_windows();
    for win in windows {
        if let Some(meeting) = engine.inspect_window(&win) {
            return Some(meeting);
        }
    }
    None
}

#[tauri::command]
fn focus_recorder_window(app_handle: AppHandle) -> Result<(), String> {
    if let Some(window) = app_handle.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn setup_tray(app_handle: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let open_item = MenuItem::with_id(app_handle, "open", "Abrir Zumo", true, None::<&str>)?;
    let record_item = MenuItem::with_id(app_handle, "record", "Iniciar Gravação", true, None::<&str>)?;
    let status_item = MenuItem::with_id(app_handle, "status", "Status: Monitorando Reuniões", false, None::<&str>)?;
    let quit_item = MenuItem::with_id(app_handle, "quit", "Sair", true, None::<&str>)?;

    let menu = Menu::with_items(app_handle, &[&open_item, &record_item, &status_item, &quit_item])?;

    let _tray = TrayIconBuilder::new()
        .tooltip("CortechX Zumo - Gravador de Reuniões")
        .menu(&menu)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "open" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "record" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                    let _ = window.emit("start-recording-action", ());
                }
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { .. } = event {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app_handle)?;

    Ok(())
}

fn start_detection_loop(app_handle: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let engine = DetectorEngine::new();
        let tracker = Arc::new(MeetingCooldownTracker::new(900)); // 15 minutos de cooldown por sala
        let mut interval = tokio::time::interval(Duration::from_millis(2500));

        loop {
            interval.tick().await;

            let windows = get_windows();
            for win in windows {
                if let Some(meeting) = engine.inspect_window(&win) {
                    if tracker.should_notify(&meeting.identifier) {
                        println!("[Detector] Reunião detectada: {:?}", meeting);

                        let platform_name = match meeting.platform {
                            detector::MeetingPlatform::GoogleMeet => "Google Meet",
                            detector::MeetingPlatform::Discord => "Discord",
                            detector::MeetingPlatform::Zoom => "Zoom",
                            detector::MeetingPlatform::MicrosoftTeams => "Microsoft Teams",
                            detector::MeetingPlatform::Generic => "Chamada Online",
                        };

                        let notif_body = format!(
                            "Chamada detectada no {}. Clique para abrir o Zumo e iniciar a gravação.",
                            platform_name
                        );

                        // 1. Notificação nativa
                        if let Err(e) = app_handle
                            .notification()
                            .builder()
                            .title("Zumo - Iniciar Gravação de Reunião?")
                            .body(&notif_body)
                            .show()
                        {
                            eprintln!("[Detector] Erro ao disparar notificação: {}", e);
                        }

                        // 2. Emite evento para o banner interativo na interface web
                        let _ = app_handle.emit("meeting-detected", &meeting);
                    }
                    break;
                }
            }
        }
    });
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            get_active_meeting,
            focus_recorder_window
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            if let Err(e) = setup_tray(&handle) {
                eprintln!("[Tray] Erro ao registrar System Tray: {}", e);
            }
            start_detection_loop(handle);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Erro ao executar aplicativo Tauri Zumo");
}
