import QtQuick
import QtQuick.Layouts
import "../.."
import "../../controls"
import "../../inputs"
import "../frame"

// Страница «Приложения по умолчанию»: браузер, файлы, почта, текст, изображения, видео, музыка
// и PDF — выпадающий список подходящих приложений на категорию (`quietline-shell defaults`).
SettingsPage {
    id: root
    title: Lang.s.appsTitle
    readonly property var categories: store.values && store.values.categories ? store.values.categories : []
    readonly property var labels: ({browser: "appsBrowser", files: "appsFiles", mail: "appsMail", text: "appsText",
                                    images: "appsImages", video: "appsVideo", music: "appsMusic", pdf: "appsPdf"})
    onOpened: store.load()

    SettingsStore {
        id: store
        command: ["quietline-shell", "defaults"]
        failure: Lang.s.appsFailed
    }

    PageNote { visible: store.values === null && store.error === ""; text: Lang.s.appsLoading }
    SettingsGroup {
        visible: root.categories.length > 0
        Repeater {
            model: root.categories
            delegate: SettingsRow {
                id: categoryRow
                required property var modelData
                label: Lang.s[root.labels[modelData.id]] || modelData.id
                note: modelData.apps.length === 0 ? Lang.s.appsNoCandidates : ""
                ShellSelect {
                    visible: categoryRow.modelData.apps.length > 0
                    label: categoryRow.label
                    minimumWidth: 200
                    placeholder: Lang.s.appsNone
                    model: categoryRow.modelData.apps.map(app => ({label: app.name}))
                    currentIndex: categoryRow.modelData.apps.findIndex(app => app.id === categoryRow.modelData.current)
                    enabled: !store.busy
                    onActivated: index => store.set({category: categoryRow.modelData.id, app: categoryRow.modelData.apps[index].id})
                }
            }
        }
    }
    PageNote { visible: store.error !== ""; color: Theme.danger; text: store.error }
    PageNote { text: Lang.s.appsNote }
}
