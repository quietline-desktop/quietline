//@ pragma Env QML_DISABLE_DISTANCEFIELD=1
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Greetd
import "greeter"

// Экран входа — отдельный процесс `qs -p …/Greeter.qml` в Hyprland экрана входа; его запускает
// `quietline-greeter` из greetd. Файл лежит в корне конфигурации: синглтоны `Theme` и `Lang`
// видны только процессу, чей корень — эта папка. Пользователи, сеансы и последний выбор — из
// `quietline-shell greeter`. Пароль уходит в greetd ответом на вопрос PAM и сразу стирается.
// После успешной проверки выбор запоминается, greetd запускает сеанс, и процесс завершается.
// Вне greetd (`Greetd.available` ложно) экран показывается, но вход сообщает об ошибке.
ShellRoot {
    id: root
    property var users: []
    property var sessions: []
    property string userName: ""
    property string sessionId: ""
    property string message: ""
    property bool messageIsError: false
    // Вопрос PAM, ответ на который ждёт поле ввода; пусто — поле спрашивает пароль.
    property string prompt: ""
    property bool echo: false
    property bool awaiting: false
    // Пароль ждёт первого вопроса PAM и стирается сразу после ответа.
    property string pendingResponse: ""
    readonly property bool busy: Greetd.state !== GreetdState.Inactive && !awaiting
    readonly property var user: users.find(item => item.name === userName) || null
    readonly property var session: sessions.find(item => item.id === sessionId) || null

    function showError(text) { message = text; messageIsError = true; }
    function resetAuth() { pendingResponse = ""; prompt = ""; echo = false; awaiting = false; }
    function chooseUser(name) {
        if (Greetd.state !== GreetdState.Inactive) Greetd.cancelSession();
        resetAuth();
        message = "";
        userName = name;
    }
    function submit(text) {
        message = "";
        messageIsError = false;
        if (!Greetd.available) { showError(Lang.s.greeterNoGreetd); return; }
        if (!user || !session) { showError(Lang.s.greeterNothingToStart); return; }
        if (awaiting) {
            awaiting = false;
            Greetd.respond(text);
            return;
        }
        if (Greetd.state !== GreetdState.Inactive) return;
        resetAuth();
        pendingResponse = text;
        Greetd.createSession(userName);
    }
    function power(action) { Quickshell.execDetached(["systemctl", action]); }
    function environment() {
        return ["XDG_SESSION_TYPE=wayland", "XDG_SESSION_DESKTOP=" + session.id,
                "XDG_CURRENT_DESKTOP=" + (session.desktopNames.length ? session.desktopNames.join(":") : session.id)];
    }

    Connections {
        target: Greetd
        function onAuthMessage(text, error, responseRequired, echoResponse) {
            if (responseRequired) {
                if (root.pendingResponse.length > 0) {
                    var response = root.pendingResponse;
                    root.pendingResponse = "";
                    Greetd.respond(response);
                } else {
                    root.prompt = text;
                    root.echo = echoResponse;
                    root.awaiting = true;
                }
            } else if (text.length > 0) {
                root.message = text;
                root.messageIsError = error;
            }
        }
        function onAuthFailure(text) {
            root.resetAuth();
            root.showError(Lang.s.lockWrongPassword);
        }
        function onReadyToLaunch() {
            root.resetAuth();
            Quickshell.execDetached(["quietline-shell", "greeter", "--remember",
                                     JSON.stringify({ user: root.userName, session: root.sessionId })]);
            Greetd.launch(root.session.command, root.environment(), true);
        }
        function onError(text) {
            root.resetAuth();
            root.showError(Lang.f(Lang.s.greeterFailed, text));
            if (Greetd.state !== GreetdState.Inactive) Greetd.cancelSession();
        }
    }

    Process {
        command: ["quietline-shell", "greeter"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(text);
                    if (data.error) { root.showError(Lang.f(Lang.s.greeterFailed, data.error)); return; }
                    root.users = data.users || [];
                    root.sessions = data.sessions || [];
                    root.userName = data.last && data.last.user ? data.last.user : "";
                    root.sessionId = data.last && data.last.session ? data.last.session : "";
                } catch (_) { root.showError(Lang.f(Lang.s.greeterFailed, "quietline-shell greeter")); }
            }
        }
    }

    Variants {
        model: Quickshell.screens
        GreeterSurface {
            required property var modelData
            screen: modelData
            context: root
        }
    }
}
