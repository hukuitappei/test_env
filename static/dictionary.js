// タブ切り替え
const commandTabBtn = document.getElementById('commandTabBtn');
const wordTabBtn = document.getElementById('wordTabBtn');
const commandDictSection = document.getElementById('commandDictSection');
const wordDictSection = document.getElementById('wordDictSection');

commandTabBtn.addEventListener('click', () => {
    commandTabBtn.classList.add('active');
    wordTabBtn.classList.remove('active');
    commandDictSection.style.display = '';
    wordDictSection.style.display = 'none';
});
wordTabBtn.addEventListener('click', () => {
    wordTabBtn.classList.add('active');
    commandTabBtn.classList.remove('active');
    wordDictSection.style.display = '';
    commandDictSection.style.display = 'none';
});

// コマンド辞書
const commandDictTable = document.getElementById('commandDictTable').querySelector('tbody');
const commandSearch = document.getElementById('commandSearch');
const commandAddForm = document.getElementById('commandAddForm');
const commandAddInput = document.getElementById('commandAddInput');

// 単語辞書
const wordDictTable = document.getElementById('wordDictTable').querySelector('tbody');
const wordSearch = document.getElementById('wordSearch');
const wordAddForm = document.getElementById('wordAddForm');
const wordAddInput = document.getElementById('wordAddInput');

// --- CRUD API ---
async function fetchDict(api) {
    const res = await fetch(api);
    return await res.json();
}
async function addDict(api, word) {
    const res = await fetch(api, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word })
    });
    return await res.json();
}
async function editDict(api, old_word, new_word) {
    const res = await fetch(api, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_word, new_word })
    });
    return await res.json();
}
async function deleteDict(api, word) {
    const res = await fetch(api, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word })
    });
    return await res.json();
}

// --- コマンド辞書UI ---
function renderCommandDictTable(data) {
    const q = commandSearch.value.trim();
    commandDictTable.innerHTML = '';
    data.filter(w => !q || w.includes(q)).forEach(word => {
        const tr = document.createElement('tr');
        const tdWord = document.createElement('td');
        tdWord.textContent = word;
        const tdOps = document.createElement('td');
        // 編集
        const editBtn = document.createElement('button');
        editBtn.textContent = '編集';
        editBtn.className = 'edit-btn';
        editBtn.onclick = () => {
            const newWord = prompt('新しいコマンド名', word);
            if (newWord && newWord !== word) {
                editDict('/api/command_dictionary', word, newWord).then(() => loadCommandDict());
            }
        };
        // 削除
        const delBtn = document.createElement('button');
        delBtn.textContent = '削除';
        delBtn.className = 'delete-btn';
        delBtn.onclick = () => {
            if (confirm('本当に削除しますか？')) {
                deleteDict('/api/command_dictionary', word).then(() => loadCommandDict());
            }
        };
        tdOps.appendChild(editBtn);
        tdOps.appendChild(delBtn);
        tr.appendChild(tdWord);
        tr.appendChild(tdOps);
        commandDictTable.appendChild(tr);
    });
}
function loadCommandDict() {
    fetchDict('/api/command_dictionary').then(data => renderCommandDictTable(data));
}
commandSearch.addEventListener('input', loadCommandDict);
commandAddForm.addEventListener('submit', e => {
    e.preventDefault();
    const word = commandAddInput.value.trim();
    if (word) {
        addDict('/api/command_dictionary', word).then(() => {
            commandAddInput.value = '';
            loadCommandDict();
        });
    }
});

// --- 単語辞書UI ---
function renderWordDictTable(data) {
    const q = wordSearch.value.trim();
    wordDictTable.innerHTML = '';
    data.filter(w => !q || w.includes(q)).forEach(word => {
        const tr = document.createElement('tr');
        const tdWord = document.createElement('td');
        tdWord.textContent = word;
        const tdOps = document.createElement('td');
        // 編集
        const editBtn = document.createElement('button');
        editBtn.textContent = '編集';
        editBtn.className = 'edit-btn';
        editBtn.onclick = () => {
            const newWord = prompt('新しい単語', word);
            if (newWord && newWord !== word) {
                editDict('/api/word_dictionary', word, newWord).then(() => loadWordDict());
            }
        };
        // 削除
        const delBtn = document.createElement('button');
        delBtn.textContent = '削除';
        delBtn.className = 'delete-btn';
        delBtn.onclick = () => {
            if (confirm('本当に削除しますか？')) {
                deleteDict('/api/word_dictionary', word).then(() => loadWordDict());
            }
        };
        tdOps.appendChild(editBtn);
        tdOps.appendChild(delBtn);
        tr.appendChild(tdWord);
        tr.appendChild(tdOps);
        wordDictTable.appendChild(tr);
    });
}
function loadWordDict() {
    fetchDict('/api/word_dictionary').then(data => renderWordDictTable(data));
}
wordSearch.addEventListener('input', loadWordDict);
wordAddForm.addEventListener('submit', e => {
    e.preventDefault();
    const word = wordAddInput.value.trim();
    if (word) {
        addDict('/api/word_dictionary', word).then(() => {
            wordAddInput.value = '';
            loadWordDict();
        });
    }
});

// 初期ロード
loadCommandDict();
loadWordDict(); 