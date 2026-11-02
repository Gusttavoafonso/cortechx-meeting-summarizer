use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum MeetingPlatform {
    GoogleMeet,
    Discord,
    Zoom,
    MicrosoftTeams,
    Generic,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowInfo {
    pub owner_name: String,
    pub title: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectedMeeting {
    pub platform: MeetingPlatform,
    pub title: String,
    pub identifier: String,
}

pub struct DetectorEngine {
    meet_regex: Regex,
    discord_regex: Regex,
    zoom_regex: Regex,
    teams_regex: Regex,
}

impl DetectorEngine {
    pub fn new() -> Self {
        Self {
            // Suporta hífen comum (-), en-dash (– \u{2013}) e em-dash (— \u{2014})
            meet_regex: Regex::new(r"(?i)Meet\s*[\u{2013}\u{2014}-]\s*([a-z0-9-]+)").unwrap(),
            discord_regex: Regex::new(r"(?i)(Discord.*(?:Voice|Voz|Chamada|Call)|\(Voice\)|\(Voz\))").unwrap(),
            zoom_regex: Regex::new(r"(?i)(Zoom\s+Meeting|Reuni[aã]o\s+Zoom|Zoom\s+Cloud\s+Meetings)").unwrap(),
            teams_regex: Regex::new(r"(?i)(Meeting|Reuni[aã]o)\s*\|\s*Microsoft\s+Teams").unwrap(),
        }
    }

    /// Analisa uma janela aberta (título e processo proprietário) e identifica se pertence a uma chamada.
    pub fn inspect_window(&self, window: &WindowInfo) -> Option<DetectedMeeting> {
        let title = window.title.trim();
        let owner = window.owner_name.trim();

        if title.is_empty() && owner.is_empty() {
            return None;
        }

        // 1. Google Meet (normalmente executado dentro do navegador)
        if let Some(caps) = self.meet_regex.captures(title) {
            let identifier = caps.get(1).map_or("meet-call", |m| m.as_str()).to_string();
            return Some(DetectedMeeting {
                platform: MeetingPlatform::GoogleMeet,
                title: title.to_string(),
                identifier: format!("google-meet:{}", identifier),
            });
        }
        if title.contains("Meet –") || title.contains("Meet -") || title.contains("Google Meet") {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::GoogleMeet,
                title: title.to_string(),
                identifier: format!("google-meet:{}", title),
            });
        }

        // 2. Discord (inspeção combinada de título e nome do processo)
        let is_discord_owner = owner.eq_ignore_ascii_case("Discord") || owner.eq_ignore_ascii_case("Discord.exe");
        if self.discord_regex.is_match(title) || (is_discord_owner && (title.contains("Voice") || title.contains("Voz") || title.contains("Call"))) {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::Discord,
                title: if !title.is_empty() { title.to_string() } else { "Discord Voice Call".to_string() },
                identifier: format!("discord:{}", if !title.is_empty() { title } else { "call" }),
            });
        }

        // 3. Zoom
        let is_zoom_owner = owner.eq_ignore_ascii_case("zoom.us") || owner.eq_ignore_ascii_case("Zoom.exe") || owner.eq_ignore_ascii_case("Zoom");
        if self.zoom_regex.is_match(title) || (is_zoom_owner && (title.contains("Meeting") || title.contains("Reunião") || title.is_empty())) {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::Zoom,
                title: if !title.is_empty() { title.to_string() } else { "Zoom Meeting".to_string() },
                identifier: format!("zoom:{}", if !title.is_empty() { title } else { "active" }),
            });
        }

        // 4. Microsoft Teams
        let is_teams_owner = owner.contains("Teams") || owner.eq_ignore_ascii_case("ms-teams.exe");
        if self.teams_regex.is_match(title) || (is_teams_owner && (title.contains("Meeting") || title.contains("Reunião"))) {
            return Some(DetectedMeeting {
                platform: MeetingPlatform::MicrosoftTeams,
                title: if !title.is_empty() { title.to_string() } else { "Teams Meeting".to_string() },
                identifier: format!("teams:{}", if !title.is_empty() { title } else { "active" }),
            });
        }

        None
    }
}

/// Evita disparar alertas repetidos para a mesma reunião a cada ciclo de polling
pub struct MeetingCooldownTracker {
    cooldown_duration: Duration,
    history: Mutex<HashMap<String, Instant>>,
}

impl MeetingCooldownTracker {
    pub fn new(cooldown_secs: u64) -> Self {
        Self {
            cooldown_duration: Duration::from_secs(cooldown_secs),
            history: Mutex::new(HashMap::new()),
        }
    }

    /// Retorna `true` se a reunião for inédita ou se o cooldown já expirou.
    pub fn should_notify(&self, identifier: &str) -> bool {
        let mut history = self.history.lock().unwrap();
        let now = Instant::now();

        if let Some(&last_seen) = history.get(identifier) {
            if now.duration_since(last_seen) < self.cooldown_duration {
                return false; // Ainda em cooldown
            }
        }

        history.insert(identifier.to_string(), now);
        true
    }

    /// Limpa o cooldown para permitir nova notificação explícita
    pub fn reset(&self, identifier: &str) {
        let mut history = self.history.lock().unwrap();
        history.remove(identifier);
    }
}
