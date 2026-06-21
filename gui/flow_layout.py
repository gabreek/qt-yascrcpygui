from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=-1, spacing=-1):
        super().__init__(parent)
        if margin != -1:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(
            margins.left(), margins.top(),
            -margins.right(), -margins.bottom()
        )
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing = self.spacing()
        if spacing < 0:
            spacing = self._default_spacing()

        for item in self._item_list:
            widget = item.widget()
            if widget:
                space_x = spacing
                space_y = spacing
                hint = widget.sizeHint()
                hint.setWidth(max(widget.minimumWidth(), min(hint.width(), widget.maximumWidth())))
                hint.setHeight(max(widget.minimumHeight(), min(hint.height(), widget.maximumHeight())))
                next_x = x + hint.width() + space_x
                if next_x - space_x > effective_rect.right() and line_height > 0:
                    x = effective_rect.x()
                    y = y + line_height + space_y
                    next_x = x + hint.width() + space_x
                    line_height = 0
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), QSize(hint.width(), hint.height())))
                x = next_x
                line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()

    def _default_spacing(self):
        style = self.parentWidget().style() if self.parentWidget() else None
        if style:
            return style.pixelMetric(style.PM_LayoutHorizontalSpacing)
        return 6
