import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Pam
import "lock"

// Экран блокировки — отдельный процесс `qs -p …/LockScreen.qml`, его запускает
// `quietline-shell lock`. Файл должен лежать в корне конфигурации: синглтоны `Theme`
// и `Lang` видны только процессу, чей корень — эта папка. Поверхность на каждом экране; пароль проверяет PAM по
// конфигурации `login`. Когда Hyprland подтвердил блокировку всех экранов, создаётся метка
// `QUIETLINE_LOCK_MARKER` для `quietline-shell lock`; после успешной проверки пароля метка
// удаляется, блокировка снимается и процесс завершается.
ShellRoot {
    id: root
    property string message: ""
    property bool messageIsError: false
    readonly property bool checking: pam.active
    // Пароль ждёт запроса PAM и сразу стирается после ответа.
    property string pendingPassword: ""
    // В этой попытке PAM уже сообщил об ошибке (например, о блокировке pam_faillock).
    property bool pamReportedError: false
    readonly property string marker: Quickshell.env("QUIETLINE_LOCK_MARKER") || ""

    function submit(password) {
        if (checking || password.length === 0) return;
        pendingPassword = password;
        pamReportedError = false;
        message = "";
        if (!pam.start()) { pendingPassword = ""; showError(Lang.s.lockStartFailed); }
    }
    function showError(text) { message = text; messageIsError = true; }

    PamContext {
        id: pam
        onPamMessage: {
            if (responseRequired) {
                respond(root.pendingPassword);
                root.pendingPassword = "";
            } else if (message.length > 0) {
                root.message = message;
                root.messageIsError = messageIsError;
                if (messageIsError) root.pamReportedError = true;
            }
        }
        onCompleted: result => {
            root.pendingPassword = "";
            if (result === PamResult.Success) {
                if (root.marker) Quickshell.execDetached(["rm", "-f", root.marker]);
                lock.locked = false;
                Qt.callLater(Qt.quit);
            } else if (root.pamReportedError) root.messageIsError = true;
            else if (result === PamResult.Failed) root.showError(Lang.s.lockWrongPassword);
            else if (result === PamResult.MaxTries) root.showError(Lang.s.lockTooManyTries);
            else root.showError(Lang.s.lockCheckFailed);
        }
    }

    WlSessionLock {
        id: lock
        locked: true
        onSecureStateChanged: { if (secure && root.marker) Quickshell.execDetached(["touch", root.marker]); }
        LockSurface { context: root }
    }
}
