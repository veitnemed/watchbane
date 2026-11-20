"""Two-section shell collection; existing library reads/actions stay authoritative."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QScrollArea,QFrame,QMessageBox,QInputDialog
from desktop.theme.scaling import layout_px
from desktop.theme.styles.cartoon import build_cartoon_style


class CollectionView:
    PAGE_SIZE = 24

    def __init__(self, legacy):
        self.legacy=legacy
        self.widget=QWidget();self.widget.setObjectName('simpleCollection');self.widget.setStyleSheet(build_cartoon_style())
        from desktop.shared.story_posters import CardPosters
        self.posters=CardPosters(self.widget)
        root=QVBoxLayout(self.widget);root.setContentsMargins(*[layout_px(24)]*4);root.setSpacing(layout_px(12))
        title_row=QHBoxLayout();title=QLabel('Ваша коллекция');title.setObjectName('storyHeading');title_row.addWidget(title,1)
        add=QPushButton('Добавить по названию…');add.clicked.connect(self._add_title);title_row.addWidget(add);root.addLayout(title_row)
        root.addWidget(QLabel('Истории на потом. И те, что уже с вами.'))
        tabs=QHBoxLayout();self.section_buttons={}
        for key,text in [('watchlist','Сохранено'),('watched','Смотрел'),('hidden','Скрыто')]:
            button=QPushButton(text);button.setCheckable(True);button.clicked.connect(self._section_callback(key));tabs.addWidget(button);self.section_buttons[key]=button
        tabs.addStretch();root.addLayout(tabs)
        self._page=0
        self.search=QLineEdit();self.search.setPlaceholderText('Найти в коллекции');self.search.setAccessibleName('Поиск в коллекции');self.search.textChanged.connect(self._reset_page);root.addWidget(self.search)
        self.status=QLabel();root.addWidget(self.status)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards=QWidget();self.layout=QVBoxLayout(self.cards);self.layout.setContentsMargins(0,0,0,0);self.layout.setSpacing(layout_px(12));self.layout.addStretch();self.scroll.setWidget(self.cards);root.addWidget(self.scroll,1)
        self.pager=QWidget()
        pages=QHBoxLayout(self.pager);pages.setContentsMargins(0,0,0,0);pages.addStretch()
        self.previous_page=QPushButton('Назад')
        self.previous_page.setAccessibleName('Предыдущая страница коллекции')
        self.previous_page.clicked.connect(lambda: self._move_page(-1))
        pages.addWidget(self.previous_page)
        self.page_status=QLabel();pages.addWidget(self.page_status)
        self.next_page=QPushButton('Дальше')
        self.next_page.setAccessibleName('Следующая страница коллекции')
        self.next_page.clicked.connect(lambda: self._move_page(1))
        pages.addWidget(self.next_page);root.addWidget(self.pager)
        self._switch_section('watchlist')

    def __getattr__(self,name):
        return getattr(self.legacy,name)

    def _section_callback(self,key):
        def clicked(_checked=False):self._switch_section(key)
        return clicked

    def _switch_section(self,section,**kwargs):
        self.legacy._switch_section(section,**kwargs)
        self._reset_page()

    def _add_title(self):
        before = {entry[0] for entry in self.legacy._watched_entries}
        self.legacy._open_add_title_dialog()
        self.reload_entries()
        if {entry[0] for entry in self.legacy._watched_entries} - before:
            self._switch_section("watched")

    def prepare_for_shutdown(self):
        self.posters.clear()
        prepare=getattr(self.legacy,"prepare_for_shutdown",None)
        if callable(prepare):prepare()

    def on_tab_activated(self):self.reload_entries()

    def reload_entries(self,**kwargs):
        self.legacy.reload_entries(**kwargs);self._render()

    def _label(self,layout,text,name=''):
        label=QLabel(str(text));label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True);label.setObjectName(name);layout.addWidget(label);return label

    def _reset_page(self, *_args):
        self._page=0
        self._render()
        self.scroll.verticalScrollBar().setValue(0)

    def _move_page(self, delta):
        self._page+=delta
        self._render()
        self.scroll.verticalScrollBar().setValue(0)

    def _render(self):
        self.posters.clear()
        while self.layout.count()>1:
            widget=self.layout.takeAt(0).widget();widget.setParent(None);widget.deleteLater()
        section=self.legacy._library_section
        for key,button in self.section_buttons.items():button.setChecked(key==section)
        query=self.search.text().strip().casefold()
        matching=[entry for entry in self.legacy._entries
                  if not query or query in str(entry[2].get('title') or entry[0]).casefold()]
        count=len(matching)
        page_count=max(1, (count+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self._page=max(0, min(self._page, page_count-1))
        start=self._page*self.PAGE_SIZE
        self.pager.setVisible(page_count>1)
        self.previous_page.setEnabled(self._page>0)
        self.next_page.setEnabled(self._page<page_count-1)
        self.page_status.setText(f'{self._page+1} из {page_count}')
        for entry in matching[start:start+self.PAGE_SIZE]:
            key,movie,card=entry;title=str(card.get('title') or key)
            frame=QFrame();frame.setObjectName('collectionCard');shell=QHBoxLayout(frame);shell.setContentsMargins(*[layout_px(16)]*4)
            poster=QLabel('Без постера');poster.setWordWrap(True);poster.setAccessibleName('Постер недоступен');poster.setObjectName('storyPoster');poster.setAlignment(Qt.AlignmentFlag.AlignCenter);poster.setFixedSize(layout_px(68),layout_px(94));shell.addWidget(poster,0,Qt.AlignmentFlag.AlignTop)
            candidate=self.legacy._action_candidates_by_key.get(key) or movie
            self.posters.bind(poster,candidate,title)
            body=QWidget();layout=QVBoxLayout(body);layout.setContentsMargins(0,0,0,0);shell.addWidget(body,1)
            self._label(layout,title,'storyTitle')
            meta=' · '.join(str(v) for v in [card.get('year'), 'Сохранено' if section=='watchlist' else 'Смотрел' if section=='watched' else 'Скрыто'] if v)
            self._label(layout,meta,'storyMuted')
            text=card.get('overview') or card.get('description') or 'Описание пока не добавлено.'
            text=str(text)
            brief=text
            compact=' '.join(text.split())
            if len(compact)>210:
                head=compact[:210]
                prefix=head.rsplit(' ',1)[0] if ' ' in head else head
                brief=prefix+'…'
            synopsis=self._label(layout,brief,'storyEvidence')
            actions=QHBoxLayout()
            if brief!=text:
                disclosure=QPushButton('Полный сюжет')
                disclosure.setCheckable(True)
                disclosure.setAccessibleName('Полный сюжет: '+title)
                def toggle(expanded, *, label=synopsis, button=disclosure,
                           full=text, preview=brief, name=title):
                    label.setText(full if expanded else preview)
                    caption='Свернуть сюжет' if expanded else 'Полный сюжет'
                    button.setText(caption)
                    button.setAccessibleName(f'{caption}: {name}')
                disclosure.toggled.connect(toggle)
                actions.addWidget(disclosure)
            options=[('Смотрел','watched'),('Убрать из сохранённого','restore'),('Скрыть','hidden')] if section=='watchlist' else [('Вернуть','restore')] if section=='hidden' else [('Оценка','score'),('Удалить…','delete')]
            for label,action in options:
                button=QPushButton(label);button.clicked.connect(self._action_callback(entry,action));actions.addWidget(button)
            actions.addStretch();layout.addLayout(actions);self.layout.insertWidget(self.layout.count()-1,frame)
        self.status.setText(f'Историй: {count}' if count else 'Здесь пока тихо. Сохраните историю из поиска.' if not query else 'По этому названию ничего нет.')

    def _action_callback(self,entry,action):
        def clicked(_checked=False):
            try:
                if action in ('score','delete'):
                    from app.use_cases.watched_library import update_user_score,delete_watched_title
                    if action=='score':
                        value,ok=QInputDialog.getItem(self.widget,'Ваша оценка','Как вам история?',['1','2','3'],editable=False)
                        if not ok:return
                        result = update_user_score(entry[0], int(value))
                        if not result.ok:
                            self.status.setText("Не удалось сохранить оценку. Попробуйте ещё раз.")
                            return
                    elif QMessageBox.question(self.widget,'Удалить из просмотренного?',str(entry[2].get('title') or entry[0]))==QMessageBox.StandardButton.Yes:
                        result=delete_watched_title(entry[0])
                        if not result.get('ok'):
                            self.status.setText('Не удалось удалить запись. Коллекция не изменена.')
                            return
                    else:return
                else:
                    from candidates import title_state_service as states
                    candidate=self.legacy._action_candidates_by_key.get(entry[0])
                    if candidate is None:return
                    if action=='watched':states.mark_watched(candidate)
                    elif action=='hidden':states.hide_candidate(candidate)
                    else:states.restore_candidate(candidate)
                self.reload_entries()
                self.legacy._notify_entries_changed()
            except Exception:self.status.setText('Не удалось сохранить действие. Попробуйте ещё раз.')
        return clicked
