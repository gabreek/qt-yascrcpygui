// gui/DynamicGridView.qml
import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0
import QtQml 6.0

Rectangle {
    id: gridRoot

    // --- Theme Properties ---
    property color backgroundColor: "black"
    property color textColor: "white"
    property color buttonBgColor: "lightgray"
    property color buttonTextColor: "black"
    property color buttonPressedColor: "gray"
    property color buttonBorderColor: "darkgray"
    property color highlightColor: "blue"
    property color highlightedTextColor: "white"
    property color altBaseColor: "lightgray"
    property bool hoverEffectEnabled: true

    color: backgroundColor

    // --- Layout Properties (set from Python) ---
    property int itemIconSize: 44
    property int itemFontSize: 9
    property int itemWidth: 98
    property int itemHeight: 98
    property int itemSpacingHorizontal: 0
    property int itemSpacingVertical: 15

    readonly property int totalItemWidth: itemWidth + itemSpacingHorizontal
    readonly property int totalItemHeight: itemHeight + itemSpacingVertical

    // --- Quick Access Properties ---
    property real quickAccessFactor: 1.0
    property bool quickAccessVisible: false
    property int minQuickAccessHeight: 48
    property string launcherPkg: ""

    // --- Rendering Settings ---
    property bool iconAntiAliasing: false
    property bool iconSmoothing: false
    property bool iconMipmaps: false

    // --- Localization Strings (set from Python via update_strings) ---
    property string allAppsText: ""
    property string settingsText: ""
    property string deleteConfigText: ""
    property string moveToText: ""
    property string createNewFolderText: ""
    property string launcherText: ""
    property string quickAccessText: ""

    // --- Signals ---
    signal launchRequested(var itemKey, var itemName)
    signal settingsRequested(var itemKey, var itemType)
    signal deleteConfigRequested(var itemKey, var itemType)
    signal pinToggled(var itemKey)
    signal iconDropped(var itemKey, var fileUrl)
    signal sectionToggled(var sectionId, bool collapsed)
    signal launchLauncherRequested()
    signal folderRequested(var itemKey)
    signal moveRequested(var itemKey, var folderName)
    signal quickAccessRequested(var itemKey, bool checked)
    signal quickAccessFactorUpdated(real factor)
    signal quickAccessVisibilityChanged(bool visible)
    signal qaLaunchRequested(var itemKey, var itemName, var itemType)

    // --- Internal Models ---
    property alias qmlInternalModel: internalModel
    ListModel { id: internalModel }
    ListModel { id: internalQuickAccessModel }

    // Quick access sizing
    readonly property int qaIconSize: Math.max(32, itemIconSize - 4)
    readonly property int qaItemSize: qaIconSize + 16

    property var itemsModel: []
    property var quickAccessModel: []
    property var folderList: []

    onItemsModelChanged: syncModel(itemsModel, internalModel, "app_")
    onQuickAccessModelChanged: syncModel(quickAccessModel, internalQuickAccessModel, "qa_")

    function syncModel(sourceData, targetModel, prefix) {
        if (!sourceData || sourceData.length === 0) {
            targetModel.clear();
            return;
        }

        var allRoles = {
            "key": "", "name": "", "icon_path": "", "item_type": "",
            "pinned": "", "isSeparator": false, "isHidden": false,
            "isCollapsed": false, "sectionId": "", "text": "",
            "ownerModel": null, "is_launcher_shortcut": false
        };

        var oldItemsMap = {};
        for (var i = 0; i < targetModel.count; i++) {
            var item = targetModel.get(i);
            var id = item.isSeparator ? ("sep_" + item.sectionId) : (prefix + item.key);
            oldItemsMap[id] = i;
        }

        for (var j = 0; j < sourceData.length; j++) {
            var newItem = sourceData[j];
            var newId = newItem.isSeparator ? ("sep_" + newItem.sectionId) : (prefix + newItem.key);
            var fullItem = Object.assign({}, allRoles, newItem);
            fullItem.ownerModel = targetModel;

            if (oldItemsMap.hasOwnProperty(newId)) {
                var oldIdx = oldItemsMap[newId];
                if (oldIdx !== j) {
                    targetModel.move(oldIdx, j, 1);
                    for (var key in oldItemsMap) {
                        var idx = oldItemsMap[key];
                        if (oldIdx < j) { if (idx > oldIdx && idx <= j) oldItemsMap[key]--; }
                        else { if (idx >= j && idx < oldIdx) oldItemsMap[key]++; }
                    }
                    oldItemsMap[newId] = j;
                }
                var currentItem = targetModel.get(j);
                for (var prop in fullItem) {
                    if (fullItem[prop] !== currentItem[prop]) {
                        targetModel.setProperty(j, prop, fullItem[prop]);
                    }
                }
                delete oldItemsMap[newId];
            } else {
                targetModel.insert(j, fullItem);
                for (var keyAdd in oldItemsMap) {
                    if (oldItemsMap[keyAdd] >= j) oldItemsMap[keyAdd]++;
                }
            }
        }

        var toRemove = [];
        for (var keyRem in oldItemsMap) toRemove.push(oldItemsMap[keyRem]);
        toRemove.sort(function(a, b) { return b - a; });
        for (var k = 0; k < toRemove.length; k++) targetModel.remove(toRemove[k]);
    }

    // --- Delegate ---
    Component {
        id: gridItemDelegate
        Item {
            id: delegateItem
            readonly property real effectiveFactor: (typeof model.ownerModel !== "undefined" && model.ownerModel === internalQuickAccessModel) ? gridRoot.quickAccessFactor : 1.0
            
            readonly property var itemData: ({
                "key": (typeof model.key !== "undefined") ? model.key : "",
                "name": (typeof model.name !== "undefined") ? model.name : "",
                "icon_path": (typeof model.icon_path !== "undefined") ? model.icon_path : "",
                "item_type": (typeof model.item_type !== "undefined") ? model.item_type : "",
                "pinned": (typeof model.pinned !== "undefined") ? model.pinned : "",
                "isSeparator": (typeof model.isSeparator !== "undefined") ? model.isSeparator : false,
                "isHidden": (typeof model.isHidden !== "undefined") ? model.isHidden : false,
                "isCollapsed": (typeof model.isCollapsed !== "undefined") ? model.isCollapsed : false,
                "sectionId": (typeof model.sectionId !== "undefined") ? model.sectionId : "",
                "text": (typeof model.text !== "undefined") ? model.text : "",
                "ownerModel": (typeof model.ownerModel !== "undefined") ? model.ownerModel : null,
                "is_launcher_shortcut": (typeof model.is_launcher_shortcut !== "undefined") ? model.is_launcher_shortcut : false
            })
            property bool isActuallyHidden: !!(itemData && itemData.isHidden)

            visible: !!(itemData) && (!isActuallyHidden || opacity > 0)
            width: (itemData && itemData.isSeparator) ? parent.width : (gridRoot.totalItemWidth * (0.7 + 0.3 * effectiveFactor))
            height: isActuallyHidden ? 0 : ((itemData && itemData.isSeparator) ? 60 : (gridRoot.minQuickAccessHeight + (gridRoot.totalItemHeight - gridRoot.minQuickAccessHeight) * effectiveFactor))
            opacity: isActuallyHidden ? 0.0 : 1.0
            clip: false

            Behavior on height { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }
            Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }

            // Hover/Click Feedback
            Rectangle {
                id: highlightRect
                anchors.centerIn: parent
                width: parent.width - 4
                height: parent.height - 4
                color: mouseArea.pressed ? Qt.lighter(gridRoot.highlightColor, 1.4) : gridRoot.highlightColor
                opacity: (mouseArea.pressed && !itemData.isSeparator) ? 0.4 : (mouseArea.containsMouse && !itemData.isSeparator ? 0.15 : 0)
                radius: 12 * (0.7 + 0.3 * effectiveFactor)
                visible: !!(itemData && !itemData.isSeparator) && gridRoot.hoverEffectEnabled
                Behavior on opacity { NumberAnimation { duration: 150 } }
                Behavior on color { ColorAnimation { duration: 100 } }
            }

            // --- Separator Content ---
            Rectangle {
                visible: !!(itemData && itemData.isSeparator)
                anchors.fill: parent
                color: gridRoot.backgroundColor

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 20
                    spacing: 10

                    Text {
                        text: (itemData && itemData.text) ? itemData.text : ""
                        Layout.fillWidth: true
                        font.pointSize: 11
                        color: gridRoot.textColor
                        verticalAlignment: Text.AlignVCenter
                    }

                    Button {
                        Layout.preferredWidth: 26
                        Layout.preferredHeight: 26
                        text: (itemData && itemData.isCollapsed) ? "+" : "-"
                        font.pixelSize: 18
                        flat: true
                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: gridRoot.textColor
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: parent.down ? gridRoot.buttonPressedColor : "transparent"
                            radius: 13
                            border.color: parent.hovered ? gridRoot.buttonBorderColor : "transparent"
                            border.width: 1
                        }
                        onClicked: {
                            var collapsed = !itemData.isCollapsed
                            var sectionId = itemData.sectionId || itemData.text
                            var targetModel = (typeof model.ownerModel !== "undefined" && model.ownerModel) ? model.ownerModel : internalModel
                            targetModel.setProperty(index, "isCollapsed", collapsed)
                            for (var i = index + 1; i < targetModel.count; i++) {
                                if (targetModel.get(i).isSeparator === true) break;
                                targetModel.setProperty(i, "isHidden", collapsed)
                            }
                            gridRoot.sectionToggled(sectionId, collapsed)
                        }
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    width: parent.width * 0.4
                    height: 1
                    color: gridRoot.buttonBorderColor
                    anchors.bottomMargin: 15
                }
            }

            // --- Context Menu ---
            Menu {
                id: contextMenu
                modal: true
                dim: false
                background: Rectangle {
                    implicitWidth: 150
                    color: gridRoot.backgroundColor
                    border.color: gridRoot.buttonBorderColor
                    radius: 10
                }
                onAboutToShow: moveSubMenu.close()

                MenuItem {
                    text: gridRoot.settingsText
                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: gridRoot.textColor
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 10
                    }
                    background: Rectangle {
                        implicitHeight: 28
                        color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                        radius: 4
                    }
                    onTriggered: {
                        if (itemData) gridRoot.settingsRequested(itemData.key, itemData.item_type)
                        contextMenu.close()
                    }
                }
                MenuItem {
                    text: gridRoot.deleteConfigText
                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: gridRoot.textColor
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 10
                    }
                    background: Rectangle {
                        implicitHeight: 28
                        color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                        radius: 4
                    }
                    onTriggered: {
                        if (itemData) gridRoot.deleteConfigRequested(itemData.key, itemData.item_type)
                        contextMenu.close()
                    }
                }
                MenuSeparator { visible: !itemData.is_launcher_shortcut }
                Menu {
                    id: moveSubMenu
                    title: gridRoot.moveToText
                    visible: !itemData.is_launcher_shortcut
                    background: Rectangle {
                        implicitWidth: 150
                        color: gridRoot.backgroundColor
                        border.color: gridRoot.buttonBorderColor
                        radius: 10
                    }

                    property bool hasAllApps: (itemData && itemData.pinned !== undefined) ? (itemData.pinned !== "") : false
                    property var filteredFolders: {
                        if (!itemData || itemData.pinned === undefined || !gridRoot.folderList) return [];
                        return gridRoot.folderList.filter(function(f) {
                            var pinnedStr = String(itemData.pinned || "")
                            var parts = pinnedStr.split(',').map(function(s) { return s.trim() })
                            return parts.indexOf(f) === -1
                        })
                    }

                    MenuItem {
                        text: gridRoot.quickAccessText
                        checkable: true
                        checked: (itemData && itemData.pinned) ? (String(itemData.pinned).indexOf("qqs") !== -1) : false
                        indicator: Rectangle {
                            implicitWidth: 18
                            implicitHeight: 18
                            x: 10
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 4
                            border.color: parent.checked ? gridRoot.highlightColor : gridRoot.buttonBorderColor
                            border.width: 1
                            color: "transparent"
                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 3
                                radius: 2
                                visible: parent.parent.checked
                                color: gridRoot.highlightColor
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: gridRoot.textColor
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 34
                        }
                        background: Rectangle {
                            implicitHeight: 28
                            color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                            radius: 4
                        }
                        onTriggered: {
                            contextMenu.close()
                            gridRoot.quickAccessRequested(itemData.key, checked)
                        }
                    }
                    MenuSeparator { visible: (itemData && itemData.pinned !== undefined) || moveSubMenu.filteredFolders.length > 0 }
                    MenuItem {
                        text: gridRoot.allAppsText
                        visible: moveSubMenu.hasAllApps
                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: gridRoot.textColor
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 10
                        }
                        background: Rectangle {
                            implicitHeight: 28
                            color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                            radius: 4
                        }
                        onTriggered: {
                            contextMenu.close()
                            gridRoot.moveRequested(itemData.key, "all")
                        }
                    }
                    MenuSeparator { visible: moveSubMenu.hasAllApps && moveSubMenu.filteredFolders.length > 0 }
                    Repeater {
                        model: moveSubMenu.filteredFolders
                        delegate: MenuItem {
                            text: modelData
                            contentItem: Text {
                                text: parent.text
                                font: parent.font
                                color: gridRoot.textColor
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 10
                            }
                            background: Rectangle {
                                implicitHeight: 28
                                color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                                radius: 4
                            }
                            onTriggered: {
                                contextMenu.close()
                                gridRoot.moveRequested(itemData.key, modelData)
                            }
                        }
                    }
                    MenuSeparator { visible: moveSubMenu.filteredFolders.length > 0 }
                    MenuItem {
                        text: gridRoot.createNewFolderText
                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: gridRoot.textColor
                            verticalAlignment: Text.AlignVCenter
                            leftPadding: 10
                        }
                        background: Rectangle {
                            implicitHeight: 28
                            color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                            radius: 4
                        }
                        onTriggered: {
                            contextMenu.close()
                            gridRoot.folderRequested(itemData.key)
                        }
                    }
                }
            }

            // --- App/Game Item Content ---
            Column {
                id: contentColumn
                visible: !!(itemData && !itemData.isSeparator)
                anchors.centerIn: parent
                width: parent.width - 10
                spacing: 8 * effectiveFactor

                Item {
                    id: iconRoot
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: gridRoot.itemIconSize * (0.8 + 0.2 * effectiveFactor)
                    height: width

                    Rectangle {
                        anchors.fill: parent
                        radius: 8 * (0.8 + 0.2 * effectiveFactor)
                        color: "transparent"
                        clip: true

                        Image {
                            id: iconImage
                            anchors.fill: parent
                            sourceSize: Qt.size(gridRoot.itemIconSize * 2, gridRoot.itemIconSize * 2)
                            source: (itemData && itemData.icon_path)
                                    ? itemData.icon_path + "?" + (gridRoot.iconMipmaps ? "hq" : "sd")
                                    : "placeholder.png"
                            fillMode: Image.PreserveAspectFit
                            antialiasing: gridRoot.iconAntiAliasing
                            smooth: gridRoot.iconSmoothing
                            mipmap: gridRoot.iconMipmaps
                            asynchronous: true
                            cache: true
                            opacity: status === Image.Ready ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: 300 } }
                        }
                    }
                }

                Text {
                    id: nameLabel
                    text: (itemData ? itemData.name : "") || ""
                    font.pointSize: gridRoot.itemFontSize * (0.8 + 0.2 * effectiveFactor)
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    width: parent.width
                    color: gridRoot.textColor
                    opacity: effectiveFactor > 0.6 ? 1 : 0
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: 250 } }
                }
            }

            // --- Input Handlers ---
            MouseArea {
                id: mouseArea
                visible: !!(itemData && !itemData.isSeparator)
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton

                onClicked: function(mouse) {
                    if (!itemData || itemData.isSeparator) return;
                    if (mouse.button === Qt.RightButton) {
                        contextMenu.popup();
                    } else {
                        if (itemData.is_launcher_shortcut) {
                            gridRoot.launchLauncherRequested();
                        } else {
                            gridRoot.launchRequested(itemData.key, itemData.name);
                        }
                    }
                }
            }

            DropArea {
                id: dropArea
                visible: !!(itemData && !itemData.isSeparator)
                anchors.fill: parent
                onDropped: function(drop) {
                    if (itemData && !itemData.isSeparator && drop.hasUrls) {
                        gridRoot.iconDropped(itemData.key, drop.urls[0].toString())
                        drop.acceptProposedAction()
                    }
                }
            }
        }
    }

    // --- Main Layout ---
    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true
        // Switch padding instantly based on the intended visibility state
        topPadding: gridRoot.quickAccessVisible ? (overlaySection.height + 15) : 0
        ScrollBar.vertical.policy: ScrollBar.AsNeeded
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        contentHeight: flowView.implicitHeight

        Flow {
            id: flowView
            width: scrollView.width
            clip: true
            Repeater {
                model: internalModel
                delegate: gridItemDelegate
            }
        }
    }

    // --- Quick Access Delegate (icon only, no text) ---
    Component {
        id: quickAccessDelegate
        Item {
            id: qaDelegateRoot
            property var itemData: ({
                "key": (typeof model.key !== "undefined") ? model.key : "",
                "name": (typeof model.name !== "undefined") ? model.name : "",
                "icon_path": (typeof model.icon_path !== "undefined") ? model.icon_path : "",
                "item_type": (typeof model.item_type !== "undefined") ? model.item_type : "",
                "is_launcher_shortcut": (typeof model.is_launcher_shortcut !== "undefined") ? model.is_launcher_shortcut : false
            })
            property bool hovered: false
            width: gridRoot.qaItemSize
            height: gridRoot.qaItemSize

            Rectangle {
                anchors.centerIn: parent
                width: gridRoot.qaItemSize - 8
                height: gridRoot.qaItemSize - 8
                radius: 10
                color: qaDelegateRoot.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.15) : "transparent"
                clip: true
                Behavior on color { ColorAnimation { duration: 150 } }

                Image {
                    anchors.centerIn: parent
                    width: gridRoot.qaIconSize
                    height: gridRoot.qaIconSize
                    sourceSize: Qt.size(gridRoot.qaIconSize * 2, gridRoot.qaIconSize * 2)
                    source: itemData.icon_path
                            ? itemData.icon_path + "?" + (gridRoot.iconMipmaps ? "hq" : "sd")
                            : "placeholder.png"
                    fillMode: Image.PreserveAspectFit
                    antialiasing: gridRoot.iconAntiAliasing
                    smooth: gridRoot.iconSmoothing
                    asynchronous: true
                    cache: true
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 300 } }
                }
            }

            HoverHandler {
                onHoveredChanged: qaDelegateRoot.hovered = hovered
                cursorShape: Qt.PointingHandCursor
            }

            TapHandler {
                onTapped: {
                    gridRoot.qaLaunchRequested(itemData.key, itemData.name, itemData.item_type)
                }
            }
        }
    }

    // --- Quick Access Overlay ---
    Rectangle {
        id: overlaySection
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 10
        anchors.topMargin: 5

        height: (internalVisible && !isClosing) ? gridRoot.qaItemSize : 0
        opacity: (internalVisible && !isClosing) ? 1.0 : 0.0

        property bool internalVisible: gridRoot.quickAccessVisible
        property bool isClosing: false

        color: gridRoot.backgroundColor
        border.color: gridRoot.buttonBorderColor
        border.width: 1
        radius: 10
        visible: opacity > 0
        clip: true

        Behavior on height { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }
        Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }

        Flickable {
            id: qaFlickable
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            contentWidth: Math.max(qaRow.implicitWidth, width)
            contentHeight: height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.HorizontalFlick
            interactive: qaRow.implicitWidth > width

            Row {
                id: qaRow
                height: parent.height
                spacing: 4
                x: Math.max(0, (qaFlickable.width - qaRow.implicitWidth) / 2)

                Repeater {
                    model: internalQuickAccessModel
                    delegate: quickAccessDelegate
                }
            }
        }
    }

    // --- Launcher Specific UI ---
    Menu {
        id: launcherMenu
        background: Rectangle {
            implicitWidth: 150
            color: gridRoot.backgroundColor
            border.color: gridRoot.buttonBorderColor
            radius: 10
        }
        MenuItem {
            text: gridRoot.settingsText
            contentItem: Text {
                text: parent.text
                font: parent.font
                color: gridRoot.textColor
                verticalAlignment: Text.AlignVCenter
                leftPadding: 10
            }
            background: Rectangle {
                implicitHeight: 28
                color: parent.hovered ? Qt.rgba(gridRoot.highlightColor.r, gridRoot.highlightColor.g, gridRoot.highlightColor.b, 0.25) : "transparent"
                radius: 4
            }
            onTriggered: gridRoot.settingsRequested(gridRoot.launcherPkg, "app")
        }
    }

    Rectangle {
        id: toggleHandle
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 4
        width: 60
        height: 8
        radius: 4
        color: handleMouseArea.containsMouse ? gridRoot.highlightColor : gridRoot.buttonBorderColor
        opacity: handleMouseArea.containsMouse ? 0.8 : 0.4
        
        Behavior on color { ColorAnimation { duration: 200 } }
        Behavior on opacity { NumberAnimation { duration: 200 } }

        MouseArea {
            id: handleMouseArea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: function(mouse) {
                gridRoot.quickAccessVisible = !gridRoot.quickAccessVisible
                gridRoot.quickAccessVisibilityChanged(gridRoot.quickAccessVisible)
            }
        }
        
        Timer {
            id: closeTimer
            interval: 300 // Matches height animation duration
            onTriggered: {
                overlaySection.internalVisible = false
                overlaySection.isClosing = false
            }
        }
    }

    onQuickAccessVisibleChanged: {
        if (quickAccessVisible) {
            overlaySection.isClosing = false
            overlaySection.internalVisible = true
        } else {
            overlaySection.isClosing = true
            closeTimer.start()
        }
    }
}
