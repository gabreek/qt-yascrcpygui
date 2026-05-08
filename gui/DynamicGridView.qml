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
            visible: !!(itemData)

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
            height: (itemData && itemData.isSeparator) ? 60 : (gridRoot.itemHeight + 25)

            // Separator content
            Rectangle {
                visible: !!(itemData && itemData.isSeparator)
                anchors.fill: parent
                color: gridRoot.backgroundColor

                Text {
                    text: itemData ? itemData.text : ""
                    anchors.fill: parent
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 11
                    color: gridRoot.textColor
                    leftPadding: 10
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
                MenuItem {
                    text: "Settings"
                    onTriggered: if (itemData) gridRoot.settingsRequested(itemData.key, itemData.item_type)
                }
                MenuItem {
                    text: "Delete Config"
                    onTriggered: if (itemData) gridRoot.deleteConfigRequested(itemData.key, itemData.item_type)
                }
                MenuItem {
                    text: itemData && itemData.is_pinned ? "Unpin" : "Pin"
                    onTriggered: if (itemData) gridRoot.pinToggled(itemData.key)
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
        internalModel.clear()
        for (var i = 0; i < itemsModel.length; i++) {
            internalModel.append(itemsModel[i])
        }
    }

    // Signals that bubble up from the delegate
    signal launchRequested(var itemKey, var itemName)
    signal settingsRequested(var itemKey, var itemType)
    signal deleteConfigRequested(var itemKey, var itemType)
    signal pinToggled(var itemKey)
    signal iconDropped(var itemKey, var fileUrl)

    ScrollView {
        id: scrollView
        anchors.fill: parent
        clip: true
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
}
