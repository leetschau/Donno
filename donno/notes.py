from typing import List
from functools import reduce
from datetime import datetime
from pathlib import Path
import subprocess
import os
import sh
import re
import shutil
import webbrowser
from donno.config import get_attr

configs = get_attr(())
NOTE_FILES = Path(configs['repo']).glob('*.md')
TEMP_FILE = 'newnote.md'
REC_FILE = Path(configs['app_home']) / 'record'
TRASH = Path(configs['app_home']) / 'trash'
DEFAULT_NOTE_LIST = 5
RES_FOLDER = Path('resources')


def update_attachments(notefn: str):
    """ See README.md > Add attachment in a note > Under the hood for
        implementation details
    """
    with open(Path(configs['repo']) / notefn, 'r') as f:
        note = f.read()
    links = re.findall(r'\[.*\]\(\)', note)
    ord_no = 0
    for link in links:
        ord_no += 1
        attfn = link[1:-3]
        attfile = Path(os.getcwd()) / attfn
        internal_path = RES_FOLDER / (Path(notefn).stem + 'att' + str(ord_no)
                                      + attfile.suffix)
        if attfile.exists():
            print(f'copy file from {attfile} to repo_path/{internal_path}')
            sh.cp(attfile, Path(configs['repo']) / internal_path)
            note = note.replace(link, f'[{attfn}]({internal_path})')
        else:
            print(f'Warning:\nAttachment {attfn} not exists in'
                  f'current folder.\nYou can run `don e ...` at the folder'
                  f'where {attfn} exists.')
    with open(Path(configs['repo']) / notefn, 'w') as f:
        f.write(note)


def add_note():
    now = datetime.now()
    created = now.strftime("%Y-%m-%d %H:%M:%S")
    current_nb = configs['default_notebook']
    header = ('Title: \nTags: \n'
              f'Notebook: {current_nb}\n'
              f'Created: {created}\n'
              f'Updated: {created}\n\n------\n\n')
    with open(TEMP_FILE, 'w') as f:
        f.write(header)
    subprocess.run(f'{configs["editor"]} {TEMP_FILE}', shell=True,
                   env={**os.environ, **configs["editor_envs"]})
    # EDITOR_CONF must be put AFTER `os.environ`, for in above syntax,
    # the latter will update the former
    # meanwhile, sh package is not suitable for TUI, so here I use subprocess
    fn = f'note{now.strftime("%y%m%d%H%M%S")}.md'
    # print(f'Save note to {REPO}/{fn}')
    if not Path(configs['repo']).exists():
        Path(configs['repo']).mkdir(parents=True)
    sh.mv(TEMP_FILE, Path(configs['repo']) / fn)
    update_attachments(fn)


def update_note(no: int):
    with open(REC_FILE) as f:
        paths = [line.strip() for line in f.readlines()]
    fn = paths[no - 1]
    subprocess.run(f'{configs["editor"]} {fn}', shell=True,
                   env={**os.environ, **configs["editor_envs"]})
    updated = datetime.fromtimestamp(
        Path(fn).stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    sh.sed('-i', f'5c Updated: {updated}', fn)
    update_attachments(fn)
    print(list_notes(DEFAULT_NOTE_LIST))


def view_note(no: int):
    with open(REC_FILE) as f:
        paths = [line.strip() for line in f.readlines()]
    fn = paths[no - 1]
    subprocess.run(f'{configs["viewer"]} {fn}', shell=True,
                   env={**os.environ, **configs["editor_envs"]})


def extract_header(path: Path) -> str:
    header_line_number = 5
    with open(path) as f:
        header = []
        for x in range(header_line_number):
            header_sections = next(f).strip().split(': ')
            header.append(header_sections[1]
                          if len(header_sections) > 1 else '')
    return (f'[{header[4]}] {header[0]} [{header[1]}] {header[2]} '
            f'{header[3]}')


def record_to_details():
    title_line = 'No. Updated, Title, Tags, Notebook, Created'
    with open(REC_FILE) as f:
        paths = [line.strip() for line in f.readlines()]
    headers = [extract_header(path) for path in paths]
    with_index = [f'{idx + 1}. {ele}' for idx, ele in enumerate(headers)]
    return '\n'.join([title_line, *with_index])


def list_notes(number):
    file_list = sorted(NOTE_FILES, key=lambda f: f.stat().st_mtime,
                       reverse=True)
    with open(REC_FILE, 'w') as f:
        f.write('\n'.join([str(path) for path in file_list[:number]]))
    return record_to_details()


def delete_note(no: int):
    with open(REC_FILE) as f:
        paths = [line.strip() for line in f.readlines()]
    if not TRASH.exists():
        TRASH.mkdir()
    sh.mv(paths[no - 1], TRASH)


def filter_word(file_list: List[str], word: str) -> List[str]:
    if len(file_list) == 0:
        return []
    try:
        res = sh.grep('-i', '-l', word, file_list)
    except sh.ErrorReturnCode_1:
        return []
    else:
        return res.stdout.decode('UTF-8').strip().split('\n')


def simple_search(word_list: List[str]) -> List[str]:
    search_res = reduce(filter_word, word_list, list(NOTE_FILES))
    if len(search_res) == 0:
        return ""
    sorted_res = sorted(search_res, key=lambda f: Path(f).stat().st_mtime,
                        reverse=True)
    with open(REC_FILE, 'w') as f:
        f.write('\n'.join([str(path) for path in sorted_res]))
    return record_to_details()


def preview_note(no: int):
    pandoc = shutil.which('pandoc')
    if pandoc is None:
        print('Pandoc not installed?\n'
              'Install it with `apt install pandoc` '
              'before running this command.')
        return
    with open(REC_FILE) as f:
        paths = [line.strip() for line in f.readlines()]
    fn = paths[no - 1]
    preview_file = Path(fn).parent / 'preview.html'
    sh.pandoc('-o', preview_file, fn)
    webbrowser.open(str(preview_file))
