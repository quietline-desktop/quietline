import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Pam

// Экран блокировки — отдельный процесс `qs -p …/lock/LockScreen.qml`, его запускает
// `quietline-shell lock`. Поверхность на каждом экране; пароль проверяет PAM по
// конфигурации `login`. После успешной проверки блокировка снимается и процесс завершается.
ShellRoot {
    id: root
    property string message: ""
    property bool messageIsError: false
    readonly property bool checking: pam.active
    // Пароль ждёт запроса PAM и сразу стирается после ответа.
    property string pendingPassword: ""

    function submit(password) {
        if (checking || password.length === 0) return;
        pendingPassword = password;
        message = "";
        if (!pam.start()) { pendingPassword = ""; showError("Не удалось начать проверку пароля"); }
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
            }
        }
        onCompleted: result => {
            root.pendingPassword = "";
            if (result === PamResult.Success) {
                lock.locked = false;
                Qt.callLater(Qt.quit);
            } else if (result === PamResult.Failed) root.showError("Неверный пароль");
            else if (result === PamResult.MaxTries) root.showError("Слишком много попыток. Подождите и попробуйте снова.");
            else root.showError("Ошибка проверки пароля");
        }
    }

    WlSessionLock {
        id: lock
        locked: true
        LockSurface { context: root }
    }
}
