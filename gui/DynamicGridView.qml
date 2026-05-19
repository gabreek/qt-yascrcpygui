// gui/DynamicGridView.qml
import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Layouts 6.0

Rectangle {
    id: gridRoot

    property color backgroundColor: "black"
    property color textColor: "white"
    property color buttonBgColor: "lightgray"
    property color buttonTextColor: "black"
    property color buttonPressedColor: "gray"
    property color buttonBorderColor: "darkgray"
    property color highlightColor: "blue"
    property color altBaseColor: "lightgray"


    color: backgroundColor

    property var itemsModel: []
    property int itemIconSize: 44
    property int itemFontSize: 9
    property int itemWidth: 80
    property int itemHeight: 105
    
    // Rendering settings
    property bool iconAntiAliasing: false
    property bool iconSmoothing: false
    property bool iconMipmaps: false

    property alias qmlInternalModel: internalModel

    ListModel {
        id: internalModel
    }

    Component {
        id: actionButtonComponent
        Button {
            font.pixelSize: 16
            display: AbstractButton.TextOnly
            background: Rectangle {
                color: parent.down ? gridRoot.buttonPressedColor : gridRoot.buttonBgColor
                radius: 11
                border.color: gridRoot.buttonBorderColor
                border.width: 1
            }
            width: 23
            height: 23
            palette.buttonText: gridRoot.textColor
        }
    }

    Component {
        id: gridItemDelegate
        Item {
            readonly property var itemData: (index < internalModel.count) ? internalModel.get(index) : undefined
            property bool isHidden: !!(itemData && itemData.isHidden)

            visible: !!(itemData) && (!isHidden || opacity > 0)

            Behavior on height { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }
            Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }

            Timer {
                id: expansionTimer
                interval: 900
                repeat: false
                onTriggered: {
                    if (secondaryActionsRow) {
                        secondaryActionsRow.opacity = 1.0
                    }
                }
            }

            width: (itemData && itemData.isSeparator) ? flowView.width : (gridRoot.itemWidth + 10)
            height: isHidden ? 0 : ((itemData && itemData.isSeparator) ? 60 : (gridRoot.itemHeight + 25))
            opacity: isHidden ? 0 : 1
            clip: true

            // Separator content
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
                            console.log("QML: Toggling section:", sectionId, "to", collapsed)
                            
                            // 1. Update the separator itself
                            internalModel.setProperty(index, "isCollapsed", collapsed)
                            
                            // 2. Loop through following items until next separator or end of model
                            for (var i = index + 1; i < internalModel.count; i++) {
                                var nextItem = internalModel.get(i)
                                
                                // Robust check for separator: check both isSeparator property and text
                                // In some versions of Winlator/Qt, isSeparator might be undefined or behave differently
                                var isNextSeparator = nextItem.isSeparator === true
                                
                                if (isNextSeparator) {
                                    console.log("QML: Next section found at", i, "- stopping.")
                                    break
                                }
                                
                                // Apply the hidden state to the item
                                internalModel.setProperty(i, "isHidden", collapsed)
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

            Menu {
                id: contextMenu
                modal: true
                dim: false // Capture clicks without darkening the screen
                
                background: Rectangle {
                    implicitWidth: 150
                    color: gridRoot.backgroundColor
                    border.color: gridRoot.buttonBorderColor
                    radius: 10
                }

                // Close the menu automatically when any action is triggered
                onClosed: { } 
                
                MenuItem {
                    text: "Settings"
                    onTriggered: {
                        if (itemData) gridRoot.settingsRequested(itemData.key, itemData.item_type)
                        contextMenu.close()
                    }
                }
                MenuItem {
                    text: "Delete Config"
                    onTriggered: {
                        if (itemData) gridRoot.deleteConfigRequested(itemData.key, itemData.item_type)
                        contextMenu.close()
                    }
                }
                Menu {
                    title: "Move to"
                    id: moveSubMenu
                    
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
                            return itemData.pinned !== f 
                        })
                    }

                    // All Apps option
                    MenuItem {
                        text: gridRoot.allAppsText
                        visible: moveSubMenu.hasAllApps
                        onTriggered: {
                            contextMenu.close()
                            gridRoot.moveRequested(itemData.key, "all")
                        }
                    }
                    
                    MenuSeparator { 
                        visible: moveSubMenu.hasAllApps && (moveSubMenu.filteredFolders.length > 0 || true)
                    }

                    Repeater {
                        model: moveSubMenu.filteredFolders
                        MenuItem {
                            text: modelData
                            onTriggered: {
                                contextMenu.close()
                                gridRoot.moveRequested(itemData.key, modelData)
                            }
                        }
                    }
                    
                    MenuSeparator { 
                        visible: moveSubMenu.filteredFolders.length > 0 
                    }

                    MenuItem {
                        text: "Create New Folder"
                        onTriggered: {
                            contextMenu.close()
                            gridRoot.folderRequested(itemData.key)
                        }
                    }
                }
            }

            // App/Game Item Content (the original Column structure)
            Column {
                visible: !!(itemData && !itemData.isSeparator) // Visible only if NOT a separator
                anchors.fill: parent // Fills the parent Item
                spacing: 10

                // Container for icon
                Item {
                    id: iconRoot
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: gridRoot.itemIconSize
                    height: gridRoot.itemIconSize

                    // Container with rounded corners for masking the image
                    Rectangle {
                        id: imageContainer
                        anchors.centerIn: parent
                        width: gridRoot.itemIconSize
                        height: gridRoot.itemIconSize
                        radius: 8
                        color: "transparent"
                        clip: true

                        Image {
                            id: iconImage
                            anchors.centerIn: parent
                            width: gridRoot.itemIconSize
                            height: gridRoot.itemIconSize
                            // sourceSize is CRITICAL for memory management. It limits the decoded image size in RAM.
                            // We use a slightly larger size than the display size for better quality when scaled.
                            sourceSize: Qt.size(gridRoot.itemIconSize * 2, gridRoot.itemIconSize * 2)
                            
                            // Query parameter is necessary to avoid "Mipmap settings changed" error when toggling HQ rendering
                            source: (itemData && itemData.icon_path) 
                                    ? itemData.icon_path + "?" + (gridRoot.iconMipmaps ? "hq" : "sd")
                                    : "placeholder.png"
                            
                            fillMode: Image.PreserveAspectFit
                            antialiasing: gridRoot.iconAntiAliasing
                            smooth: gridRoot.iconSmoothing
                            mipmap: gridRoot.iconMipmaps
                            asynchronous: true
                            cache: false
                        }
                    }
                }

                Text {
                    id: nameLabel
                    text: (itemData ? itemData.name : "") || "" // Adicionar fallback para string vazia
                    font.pointSize: gridRoot.itemFontSize
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    width: parent.width
                    color: gridRoot.textColor
                }
            }

            // MouseArea and DropArea for the normal item
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
                        gridRoot.launchRequested(itemData.key, itemData.name);
                    }
                }
            }

            DropArea {
                id: dropArea
                visible: !!(itemData && !itemData.isSeparator)
                anchors.fill: parent
                onDropped: function(drop) {
                    if (itemData && !itemData.isSeparator && drop.hasUrls) {
                        let url = drop.urls[0] // This is the QUrl object
                        gridRoot.iconDropped(itemData.key, url.toString()) // Pass the raw URL string to Python
                        drop.acceptProposedAction()
                    }
                }
            }
        }
    }


    // Populate internalModel when itemsModel changes
    onItemsModelChanged: {
        if (!itemsModel) {
            internalModel.clear();
            return;
        }

        // 1. Map existing items by ID
        var oldItemsMap = {};
        for (var i = 0; i < internalModel.count; i++) {
            var item = internalModel.get(i);
            var id = item.isSeparator ? ("sep_" + item.sectionId) : ("app_" + item.key);
            oldItemsMap[id] = i;
        }

        // 2. Sync model with new data
        for (var j = 0; j < itemsModel.length; j++) {
            var newItem = itemsModel[j];
            var newId = newItem.isSeparator ? ("sep_" + newItem.sectionId) : ("app_" + newItem.key);
            
            if (oldItemsMap.hasOwnProperty(newId)) {
                var oldIdx = oldItemsMap[newId];
                
                // Move if necessary
                if (oldIdx !== j) {
                    internalModel.move(oldIdx, j, 1);
                    // Update indices for all items in oldItemsMap that might have shifted
                    for (var key in oldItemsMap) {
                        var idx = oldItemsMap[key];
                        if (oldIdx < j) { // Moved down
                            if (idx > oldIdx && idx <= j) oldItemsMap[key]--;
                        } else { // Moved up
                            if (idx >= j && idx < oldIdx) oldItemsMap[key]++;
                        }
                    }
                    oldItemsMap[newId] = j;
                }
                
                // Update properties
                var currentItem = internalModel.get(j);
                for (var prop in newItem) {
                    if (newItem[prop] !== currentItem[prop]) {
                        internalModel.setProperty(j, prop, newItem[prop]);
                    }
                }
                // Remove from map to signal it shouldn't be deleted
                delete oldItemsMap[newId];
            } else {
                // New item
                internalModel.insert(j, newItem);
                // Shift indices in map
                for (var keyAdd in oldItemsMap) {
                    if (oldItemsMap[keyAdd] >= j) oldItemsMap[keyAdd]++;
                }
            }
        }

        // 3. Remove what's left in oldItemsMap
        // Sort indices descending to remove without shifting others
        var toRemove = [];
        for (var keyRem in oldItemsMap) {
            toRemove.push(oldItemsMap[keyRem]);
        }
        toRemove.sort(function(a, b) { return b - a; });
        
        for (var k = 0; k < toRemove.length; k++) {
            internalModel.remove(toRemove[k]);
        }
    }

    // Signals that bubble up from the delegate
    signal launchRequested(var itemKey, var itemName)
    signal settingsRequested(var itemKey, var itemType)
    signal deleteConfigRequested(var itemKey, var itemType)
    signal pinToggled(var itemKey)
    signal iconDropped(var itemKey, var fileUrl)
    signal sectionToggled(var sectionId, bool collapsed)
    signal launchLauncherRequested()
    signal folderRequested(var itemKey)
    signal moveRequested(var itemKey, var folderName)

    property var folderList: []
    property string allAppsText: "All Apps"

    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true
        topPadding: overlaySection.visible ? overlaySection.height : 0
        ScrollBar.vertical.policy: ScrollBar.AsNeeded
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        contentHeight: flowView.implicitHeight

        Flow {
            id: flowView
            width: scrollView.width

            Repeater {
                model: internalModel
                delegate: gridItemDelegate
            }
        }
    }

    property string launcherPkg: ""

    // Persistent Overlay Section
    Rectangle {
        id: overlaySection
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 10
        height: visible ? 90 : 0
        color: gridRoot.backgroundColor
        border.color: gridRoot.buttonBorderColor
        border.width: 1
        radius: 10
        visible: false
        clip: true
        Behavior on height { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }

        Column {
            anchors.centerIn: parent
            spacing: 2
            
            // Launcher Icon Button
            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: gridRoot.itemIconSize
                height: gridRoot.itemIconSize

                Image {
                    id: launcherImage
                    source: "launcher.png"
                    width: gridRoot.itemIconSize
                    height: gridRoot.itemIconSize
                    fillMode: Image.PreserveAspectFit
                    
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: function(mouse) {
                            if (mouse.button === Qt.RightButton) {
                                launcherMenu.popup();
                            } else {
                                gridRoot.launchLauncherRequested()
                            }
                        }
                    }
                }
            }
            Text {
                text: "Launcher"
                color: gridRoot.textColor
                font.pointSize: gridRoot.itemFontSize
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }
    }

    Menu {
        id: launcherMenu
        MenuItem {
            text: "Settings"
            onTriggered: gridRoot.settingsRequested(gridRoot.launcherPkg, "app")
        }
    }

    // Discrete Toggle Handle
    Rectangle {
        id: toggleHandle
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 2
        width: 60
        height: 6
        radius: 3
        color: gridRoot.buttonBorderColor
        opacity: 0.5
        
        MouseArea {
            anchors.fill: parent
            onClicked: overlaySection.visible = !overlaySection.visible
        }
    }
}
