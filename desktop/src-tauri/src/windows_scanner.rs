use crate::detector::WindowInfo;

#[cfg(target_os = "windows")]
pub fn list_visible_windows() -> Vec<WindowInfo> {
    use std::ffi::OsString;
    use std::os::windows::ffi::OsStringExt;
    use windows_sys::Win32::Foundation::{BOOL, HWND, LPARAM};
    use windows_sys::Win32::System::Threading::{
        OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION,
    };
    use windows_sys::Win32::System::ProcessStatus::GetProcessImageFileNameW;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        EnumWindows, GetWindowTextLengthW, GetWindowTextW, GetWindowThreadProcessId,
        IsWindowVisible,
    };

    let mut windows: Vec<WindowInfo> = Vec::new();

    unsafe extern "system" fn enum_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let windows_ptr = lparam as *mut Vec<WindowInfo>;
        if IsWindowVisible(hwnd) != 0 {
            let length = GetWindowTextLengthW(hwnd);
            let mut title = String::new();
            if length > 0 {
                let mut buffer: Vec<u16> = vec![0; (length + 1) as usize];
                let copied = GetWindowTextW(hwnd, buffer.as_mut_ptr(), length + 1);
                if copied > 0 {
                    let os_str = OsString::from_wide(&buffer[..copied as usize]);
                    if let Ok(t) = os_str.into_string() {
                        title = t;
                    }
                }
            }

            // Inspeciona nome do processo / executável
            let mut process_id: u32 = 0;
            GetWindowThreadProcessId(hwnd, &mut process_id);
            let mut owner_name = String::new();

            if process_id > 0 {
                let proc_handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, process_id);
                if !proc_handle.is_null() {
                    let mut img_buf: Vec<u16> = vec![0; 512];
                    let img_len = GetProcessImageFileNameW(proc_handle, img_buf.as_mut_ptr(), 512);
                    if img_len > 0 {
                        let os_str = OsString::from_wide(&img_buf[..img_len as usize]);
                        if let Ok(path) = os_str.into_string() {
                            if let Some(exe_name) = path.split('\\').last() {
                                owner_name = exe_name.to_string();
                            }
                        }
                    }
                }
            }

            if !title.trim().is_empty() || !owner_name.trim().is_empty() {
                (*windows_ptr).push(WindowInfo { owner_name, title });
            }
        }
        1
    }

    unsafe {
        EnumWindows(Some(enum_proc), &mut windows as *mut _ as LPARAM);
    }

    windows
}

#[cfg(not(target_os = "windows"))]
pub fn list_visible_windows() -> Vec<WindowInfo> {
    Vec::new()
}
