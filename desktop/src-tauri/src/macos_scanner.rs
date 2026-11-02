use crate::detector::WindowInfo;

#[cfg(target_os = "macos")]
pub fn list_visible_windows() -> Vec<WindowInfo> {
    use core_foundation::array::CFArray;
    use core_foundation::base::TCFType;
    use core_foundation::dictionary::CFDictionary;
    use core_foundation::string::CFString;
    use core_graphics::window::*;
    use std::ffi::c_void;

    let mut windows = Vec::new();

    unsafe {
        let window_list_info = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
            kCGNullWindowID,
        );

        if window_list_info.is_null() {
            return windows;
        }

        let array: CFArray = CFArray::wrap_under_create_rule(window_list_info);
        for item in array.iter() {
            let dict: CFDictionary = CFDictionary::wrap_under_get_rule(*item as *const _);

            // 1. kCGWindowOwnerName (Não requer permissão de Screen Recording no macOS)
            let mut owner_name = String::new();
            let key_owner = CFString::from_static_string("kCGWindowOwnerName");
            let mut owner_ptr: *const c_void = std::ptr::null();
            if dict.find(key_owner.as_concrete_TypeRef() as *const c_void, &mut owner_ptr) && !owner_ptr.is_null() {
                let cf_str: CFString = CFString::wrap_under_get_rule(owner_ptr as *const _);
                owner_name = cf_str.to_string();
            }

            // 2. kCGWindowName (Título da janela)
            let mut window_title = String::new();
            let key_name = CFString::from_static_string("kCGWindowName");
            let mut name_ptr: *const c_void = std::ptr::null();
            if dict.find(key_name.as_concrete_TypeRef() as *const c_void, &mut name_ptr) && !name_ptr.is_null() {
                let cf_str: CFString = CFString::wrap_under_get_rule(name_ptr as *const _);
                window_title = cf_str.to_string();
            }

            if !owner_name.trim().is_empty() || !window_title.trim().is_empty() {
                windows.push(WindowInfo {
                    owner_name,
                    title: window_title,
                });
            }
        }
    }

    windows
}

#[cfg(not(target_os = "macos"))]
pub fn list_visible_windows() -> Vec<WindowInfo> {
    Vec::new()
}
