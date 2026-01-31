// gui/DynamicGridView.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

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
    property int itemIconSize: 40
    property int itemFontSize: 9
    property int itemWidth: 80
    property int itemHeight: 105

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

            // App/Game Item Content (the original Column structure)
            Column {
                visible: !!(itemData && !itemData.isSeparator) // Visible only if NOT a separator
                anchors.fill: parent // Fills the parent Item

                // Container for icon and overlay
                Item {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: gridRoot.itemIconSize
                    height: gridRoot.itemIconSize + 10

                    Image {
                        id: iconImage
                        anchors.centerIn: parent
                        width: gridRoot.itemIconSize
                        height: gridRoot.itemIconSize
                        source: (itemData ? itemData.icon_path : "") || "placeholder.png"
                        fillMode: Image.PreserveAspectFit
                        antialiasing: true
                    }

                    // Action buttons overlay - NEW LOGIC
                    Item {
                        id: actionsContainer
                        anchors.top: parent.top
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Math.max(optionsLoader.width, secondaryActionsRow.width)
                        height: Math.max(optionsLoader.height, secondaryActionsRow.height)
                        opacity: mouseArea.containsMouse ? 1.0 : 0.0
                        Behavior on opacity { OpacityAnimator { duration: 150 } }

                        // This holds the secondary buttons (S, D, P)
                        Row {
                            id: secondaryActionsRow
                            spacing: 2
                            opacity: 0.0 // Initially hidden
                            Behavior on opacity { OpacityAnimator { duration: 150 } }


                            Loader {
                                id: settingsButtonLoader
                                property var buttonText: "S"
                                sourceComponent: (itemData && (itemData.item_type === 'app' || itemData.item_type === 'winlator_game')) ? actionButtonComponent : undefined
                                onLoaded: {
                                    item.text = buttonText;
                                    item.clicked.connect(function() {
                                        if (itemData) gridRoot.settingsRequested(itemData.key, itemData.item_type);
                                    });
                                }
                                width: 28
                                height: 28
                            }
                            Loader {
                                id: deleteButtonLoader
                                property var buttonText: "D"
                                sourceComponent: (itemData && (itemData.item_type === 'app' || itemData.item_type === 'winlator_game')) ? actionButtonComponent : undefined
                                onLoaded: {
                                    item.text = buttonText
                                    item.clicked.connect(function() {
                                        if (itemData) gridRoot.deleteConfigRequested(itemData.key, itemData.item_type)
                                    })
                                }
                                width: 28
                                height: 28
                            }
                            Loader {
                                id: pinButtonLoader
                                property var buttonText: itemData && itemData.is_pinned ? "P" : "p"
                                sourceComponent: (itemData && (itemData.item_type === 'app' && !itemData.is_launcher_shortcut)) ? actionButtonComponent : undefined
                                onLoaded: {
                                    item.text = buttonText
                                    item.clicked.connect(function() {
                                        if (itemData) gridRoot.pinToggled(itemData.key)
                                    })
                                }
                                width: 28
                                height: 28
                            }
                        }

                        // The primary "Options" button
                        Loader {
                            id: optionsLoader
                            property var buttonText: "..."
                            opacity: secondaryActionsRow.opacity === 1.0 ? 0.0 : 1.0
                            sourceComponent: actionButtonComponent
                            onLoaded: { item.text = buttonText }
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

                property string currentHoverTarget: ""

                onPositionChanged: function(mouse) {
                    if (!actionsContainer || !optionsLoader) return;
                    var mappedPoint = mapToItem(actionsContainer, mouse.x, mouse.y);
                    if (optionsLoader.contains(mappedPoint)) {
                        if (currentHoverTarget !== "options") {
                            currentHoverTarget = "options";
                            expansionTimer.start();
                        }
                    }
                    else {
                        if (currentHoverTarget === "options") {
                            currentHoverTarget = "item";
                            expansionTimer.stop();
                        }
                    }
                }

                onClicked: function(mouse) {
                    if (!itemData || itemData.isSeparator) return;
                    mouse.accepted = true; //This area handles all clicks on the delegate

                    // Check for button clicks first
                    var mappedPoint = mapToItem(actionsContainer, mouse.x, mouse.y);
                    if (actionsContainer.contains(mappedPoint)) {

                        if (settingsButtonLoader.item && settingsButtonLoader.item.contains(settingsButtonLoader.item.mapFromItem(mouseArea, mouse.x, mouse.y))) {
                            settingsButtonLoader.item.clicked();
                            return;
                        }
                        if (deleteButtonLoader.item && deleteButtonLoader.item.contains(deleteButtonLoader.item.mapFromItem(mouseArea, mouse.x, mouse.y))) {
                            deleteButtonLoader.item.clicked();
                            return;
                        }
                        if (pinButtonLoader.item && pinButtonLoader.item.contains(pinButtonLoader.item.mapFromItem(mouseArea, mouse.x, mouse.y))) {
                            pinButtonLoader.item.clicked();
                            return;
                        }
                        // If click is on actionsContainer but not a specific button, do nothing.

                    } else {
                        // If click was outside button area, launch the app
                        gridRoot.launchRequested(itemData.key, itemData.name);
                    }
                }
                onEntered: {
                    currentHoverTarget = "item";
                }
                onExited: function() {
                    currentHoverTarget = "none";
                    expansionTimer.stop();
                    if (secondaryActionsRow) {
                        secondaryActionsRow.opacity = 0.0;
                    }
                }
            }

            DropArea {
                id: dropArea
                visible: !!(itemData && !itemData.isSeparator)
                anchors.fill: parent
                onDropped: function(drop) {
                    if (itemData && !itemData.isSeparator && drop.hasUrls) {
                        let url = drop.urls[0]
                        let localFile = url.toLocalFile()
                        if (localFile.endsWith(".png") || localFile.endsWith(".jpg") || localFile.endsWith(".jpeg")) {
                            gridRoot.iconDropped(itemData.key, url)
                            drop.acceptProposedAction()
                        }
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
