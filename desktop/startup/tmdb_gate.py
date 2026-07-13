"""Blocking TMDb startup gate shown before the main desktop shell."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from common.release import release_signature
from desktop.i18n import tr
from desktop.shared.brand_assets import tmdb_logo_label, watchbane_wordmark_label
from desktop.startup.network_tools import (
    TmdbDiagnosticsWorker,
    TmdbRecoveryToolsDialog,
    format_tmdb_diagnostic_summary,
)
from desktop.startup.worker import TmdbStartupReadinessWorker, TmdbStartupValidateWorker
from desktop.theme.scaling import font_px, scale_px
from desktop.theme.styles.startup import build_startup_gate_style
from desktop.theme.tokens import (
    FONT_BASE,
    FONT_DIALOG_TITLE,
    FONT_FAMILY,
    FONT_SMALL,
    SPACING_LARGE,
    SPACING_MEDIUM,
    SPACING_SMALL,
)


class TmdbStartupGateView(QWidget):
    """Minimal premium gate for TMDb network check and token entry."""

    passed = pyqtSignal()
    localModeRequested = pyqtSignal()
    attentionRequired = pyqtSignal()

    def __init__(self, parent=None, *, autostart: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("startupGateRoot")
        self.setStyleSheet(build_startup_gate_style())
        self._network_ok = False
        self._busy = False
        self._network_worker: TmdbStartupReadinessWorker | None = None
        self._validate_worker: TmdbStartupValidateWorker | None = None
        self._diagnostics_worker: TmdbDiagnosticsWorker | None = None
        self._build_ui()
        if autostart:
            self.start_readiness_probe()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(scale_px(32), scale_px(32), scale_px(32), scale_px(32))
        outer.addStretch(1)

        card = QFrame()
        card.setObjectName("startupGateCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        card.setMinimumWidth(scale_px(540))
        card.setMaximumWidth(scale_px(660))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            scale_px(40),
            scale_px(34),
            scale_px(40),
            scale_px(34),
        )
        card_layout.setSpacing(scale_px(SPACING_SMALL + 2))

        title = QLabel(tr("startup.tmdb.title"))
        title.setObjectName("startupGateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(FONT_FAMILY, font_px(FONT_DIALOG_TITLE))
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)

        subtitle = QLabel(tr("startup.tmdb.subtitle"))
        subtitle.setObjectName("startupGateSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont(FONT_FAMILY, font_px(FONT_SMALL)))

        self._network_label = QLabel(tr("startup.tmdb.network.checking"))
        self._network_label.setObjectName("startupGateNetworkStatus")
        self._network_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._network_label.setWordWrap(True)
        self._network_label.setMinimumHeight(scale_px(68))
        self._network_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._network_label.setFont(QFont(FONT_FAMILY, font_px(FONT_SMALL)))

        diagnostics_row = QHBoxLayout()
        self._diagnostics_button = QPushButton(tr("startup.tmdb.diagnostics.run"))
        self._diagnostics_button.setObjectName("startupDiagnosticButton")
        self._diagnostics_button.clicked.connect(self._run_diagnostics)
        self._tools_button = QPushButton(tr("startup.tmdb.tools.open"))
        self._tools_button.setObjectName("startupToolsButton")
        self._tools_button.clicked.connect(self._open_recovery_tools)
        diagnostics_row.addWidget(self._diagnostics_button)
        diagnostics_row.addWidget(self._tools_button)

        token_caption = QLabel(tr("startup.tmdb.token.label"))
        token_caption.setObjectName("startupGateTokenLabel")
        token_caption.setFont(QFont(FONT_FAMILY, font_px(FONT_BASE)))

        self._token_input = QLineEdit()
        self._token_input.setObjectName("startupTokenInput")
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_input.setPlaceholderText(tr("startup.tmdb.token.placeholder"))
        self._token_input.setEnabled(False)
        self._token_input.setMinimumHeight(scale_px(44))
        self._token_input.returnPressed.connect(self._on_continue_clicked)
        self._token_input.textChanged.connect(self._on_token_changed)

        hint = QLabel(tr("startup.tmdb.token.hint"))
        hint.setObjectName("startupGateHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        hint.setMinimumHeight(scale_px(52))
        hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hint.setFont(QFont(FONT_FAMILY, font_px(FONT_SMALL)))

        attribution = QFrame()
        attribution.setObjectName("startupTmdbAttribution")
        attribution.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        attribution_layout = QHBoxLayout(attribution)
        attribution_layout.setContentsMargins(
            scale_px(12), scale_px(10), scale_px(12), scale_px(10)
        )
        attribution_layout.setSpacing(scale_px(12))
        attribution_layout.addWidget(tmdb_logo_label(scale_px(46)), 0, Qt.AlignmentFlag.AlignTop)
        attribution_text = QLabel(tr("startup.tmdb.attribution"))
        attribution_text.setObjectName("startupTmdbAttributionText")
        attribution_text.setWordWrap(True)
        attribution_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        attribution_text.setMinimumHeight(scale_px(58))
        attribution_layout.addWidget(attribution_text, 1)

        self._error_label = QLabel("")
        self._error_label.setObjectName("startupGateError")
        self._error_label.setWordWrap(True)
        self._error_label.setMinimumHeight(scale_px(34))
        self._error_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._error_label.setFont(QFont(FONT_FAMILY, font_px(FONT_SMALL)))
        self._error_label.hide()

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self._continue_button = QPushButton(tr("startup.tmdb.continue"))
        self._continue_button.setObjectName("startupPrimaryButton")
        self._continue_button.setEnabled(False)
        self._continue_button.setMinimumWidth(scale_px(180))
        self._continue_button.setMinimumHeight(scale_px(42))
        self._continue_button.clicked.connect(self._on_continue_clicked)
        self._offline_button = QPushButton(tr("startup.tmdb.continue_offline"))
        self._offline_button.setObjectName("startupSecondaryButton")
        self._offline_button.clicked.connect(self.localModeRequested.emit)
        self._offline_button.setMinimumHeight(scale_px(42))
        button_row.addWidget(self._offline_button)
        button_row.addWidget(self._continue_button)
        button_row.addStretch(1)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(scale_px(SPACING_SMALL + 2))
        card_layout.addWidget(self._network_label)
        card_layout.addLayout(diagnostics_row)
        card_layout.addSpacing(scale_px(SPACING_MEDIUM))
        card_layout.addWidget(token_caption)
        card_layout.addWidget(self._token_input)
        card_layout.addWidget(hint)
        card_layout.addWidget(self._error_label)
        card_layout.addSpacing(scale_px(SPACING_SMALL))
        card_layout.addLayout(button_row)
        card_layout.addSpacing(scale_px(SPACING_MEDIUM))
        card_layout.addWidget(attribution)
        card_layout.addSpacing(scale_px(SPACING_SMALL))
        card_layout.addWidget(
            watchbane_wordmark_label(scale_px(190), scale_px(40)),
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        release_label = QLabel(release_signature())
        release_label.setObjectName("startupReleaseVersion")
        release_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        release_label.setWordWrap(True)
        card_layout.addWidget(release_label)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(2)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._continue_button.setEnabled(
            busy is False and self._network_ok and self._token_input.text().strip() != ""
        )
        self._token_input.setEnabled(busy is False and self._network_ok)

    def _show_error(self, message: str) -> None:
        if message.strip() == "":
            self._error_label.hide()
            return
        self._error_label.setText(message)
        self._error_label.show()

    def _start_network_probe(self) -> None:
        self._network_label.setText(tr("startup.tmdb.network.checking"))
        worker = TmdbStartupReadinessWorker(parent=self)
        worker.completed.connect(self._on_network_probe_finished)
        worker.finished.connect(worker.deleteLater)
        self._network_worker = worker
        worker.start()

    def _run_diagnostics(self) -> None:
        if self._diagnostics_worker is not None:
            return
        self._diagnostics_button.setEnabled(False)
        self._diagnostics_button.setText(tr("startup.tmdb.diagnostics.running"))
        self._network_label.setText(tr("startup.tmdb.diagnostics.running_detail"))
        worker = TmdbDiagnosticsWorker(parent=self)
        worker.completed.connect(self._on_diagnostics_finished)
        worker.finished.connect(worker.deleteLater)
        self._diagnostics_worker = worker
        worker.start()

    def _on_diagnostics_finished(self, result: dict) -> None:
        self._diagnostics_worker = None
        self._diagnostics_button.setEnabled(True)
        self._diagnostics_button.setText(tr("startup.tmdb.diagnostics.run"))
        message, severity = format_tmdb_diagnostic_summary(result)
        self._network_label.setProperty("diagnosticSeverity", severity)
        self._network_label.setText(message)
        self._network_label.style().unpolish(self._network_label)
        self._network_label.style().polish(self._network_label)
        network_available = result.get("networkPathAvailable") is True
        self._network_ok = network_available
        self._token_input.setEnabled(network_available and not self._busy)
        self._continue_button.setEnabled(
            network_available and not self._busy and bool(self._token_input.text().strip())
        )

    def _open_recovery_tools(self) -> None:
        dialog = TmdbRecoveryToolsDialog(self)
        dialog.exec()

    def start_readiness_probe(self) -> None:
        """Check credentials while the main shell stays visible on the fast path."""
        if self._network_worker is None:
            self._start_network_probe()

    def _on_token_changed(self, _text: str) -> None:
        if self._busy:
            return
        self._continue_button.setEnabled(
            self._network_ok and self._token_input.text().strip() != ""
        )

    def _on_network_probe_finished(self, result: dict) -> None:
        self._network_worker = None
        if result.get("ready") is True:
            self._network_ok = True
            self._network_label.setText(tr("startup.tmdb.network.ok"))
            self.passed.emit()
            return

        network = result.get("network") if isinstance(result.get("network"), dict) else result
        if network.get("ok") is True:
            self._network_ok = True
            self._network_label.setText(tr("startup.tmdb.network.ok"))
            self._token_input.setEnabled(True)
            self._continue_button.setEnabled(self._token_input.text().strip() != "")
            error_code = str(result.get("error") or "")
            if error_code in {"invalid_token", "validation_failed"}:
                mapping = {
                    "invalid_token": "startup.tmdb.error.invalid_token",
                    "validation_failed": "startup.tmdb.error.validation_failed",
                }
                self._show_error(tr(mapping[error_code]))
            self.attentionRequired.emit()
            return

        dns = network.get("dns") if isinstance(network.get("dns"), dict) else {}
        if (
            result.get("error") == "dns_blocked"
            or network.get("error") == "dns_blocked"
            or dns.get("blocked_localhost")
        ):
            self._network_label.setText(tr("startup.tmdb.network.blocked"))
        else:
            self._network_label.setText(tr("startup.tmdb.network.unreachable"))
        self._network_ok = False
        self._token_input.setEnabled(False)
        self._continue_button.setEnabled(False)
        self.attentionRequired.emit()

    def _on_continue_clicked(self) -> None:
        if self._busy or self._network_ok is False:
            return
        token = self._token_input.text().strip()
        if token == "":
            self._show_error(tr("startup.tmdb.error.missing_token"))
            return

        self._show_error("")
        self._set_busy(True)
        worker = TmdbStartupValidateWorker(token, parent=self)
        worker.completed.connect(self._on_validate_finished)
        worker.finished.connect(worker.deleteLater)
        self._validate_worker = worker
        worker.start()

    def _on_validate_finished(self, result: dict) -> None:
        self._validate_worker = None
        self._set_busy(False)
        if result.get("ready") is True:
            self._show_error("")
            self.passed.emit()
            return

        error_code = str(result.get("error") or "invalid_token")
        mapping = {
            "dns_blocked": "startup.tmdb.error.dns_blocked",
            "network_unreachable": "startup.tmdb.error.network_unreachable",
            "missing_token": "startup.tmdb.error.missing_token",
            "invalid_token": "startup.tmdb.error.invalid_token",
            "validation_failed": "startup.tmdb.error.validation_failed",
            "save_failed": "startup.tmdb.error.save_failed",
        }
        self._show_error(tr(mapping.get(error_code, "startup.tmdb.error.invalid_token")))
