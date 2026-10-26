pragma Singleton
import QtQuick

// Открытое сейчас всплывающее окно оболочки: одновременно открыто не больше одного.
QtObject { property var current: null }
