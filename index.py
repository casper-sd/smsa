import os
from os import path
from glob import glob
import pytesseract
import subprocess
import shutil
from pdf2image import convert_from_path
from sqlitedict import SqliteDict
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

os.system('color')
prompts = ['Index']
d = u"\u001b[33m>\u001b[0m"
_dir_ = ''
command = ''
res = []
curr_res = 0
Base = declarative_base()
engine = create_engine('sqlite:///database.sqlite3')
session = sessionmaker(bind=engine)()
args = ['resource', 'tesseract', 'acrobat', 'poppler']


class File(Base):
    __tablename__ = 'file'
    serial = Column(Integer, autoincrement=True, primary_key=True)
    dir_name = Column(String, nullable=False)
    filename = Column(String, nullable=False)


class Record(Base):
    __tablename__ = 'record'
    serial = Column(Integer, ForeignKey(File.serial), primary_key=True)
    page_number = Column(Integer, primary_key=True)
    content = Column(Text)


if not os.path.isfile('database.sqlite3'):
    Base.metadata.create_all(engine)
dic = SqliteDict('database.sqlite3', autocommit=True)


def check_path(arg):
    global index
    prompt = ''
    if arg == 'resource':
        prompt = 'Resource Directory Path'
    elif arg == 'tesseract':
        prompt = 'Tesseract OCR Path'
    elif arg == 'acrobat':
        prompt = 'Acrobat PDF Reader Path'
    elif arg == 'poppler':
        prompt = 'Poppler Path'

    if arg in dic:
        if not os.path.exists(dic[arg]):
            del dic[arg]

    while arg not in dic:
        p = input(prompt + d + d + ' ').lower()
        if os.path.exists(p):
            dic[arg] = p
            if arg == 'resource':
                index = [str(f.name).lower() for f in os.scandir(dic['resource']) if f.is_dir()]
        else:
            print('Can\'t locate the file specified. Try again')


def set_path(arg):
    if arg == 'resource':
        print('Warning: Files in {} will be inaccessible until you set the resource directory back to this path.'
              .format(dic['resource']))
    print('Type "confirm" to proceed or "back" to terminate')
    conf = input(d + d + ' ').lower()
    if conf == 'back':
        return
    elif conf == 'confirm':
        if arg in dic:
            del dic[arg]
        check_path(arg)
    else:
        print('Undefined command.')
        return


# ............................................................................................
print('Study Material Search Application ~ Version 1.0')
print('Hint: You can type "back" or "exit" at any step. All commands are case-insensitive\n')
for ar in args:
    check_path(ar)
pytesseract.pytesseract.tesseract_cmd = dic['tesseract']
index = [str(f.name).lower() for f in os.scandir(dic['resource']) if f.is_dir()]


def search_database(search_str):
    keys = search_str.split(',')
    results = {}
    session.begin()
    for k in keys:
        recs = session.query(File, Record).join(Record).filter(File.dir_name == _dir_,
                                                               Record.content.contains(k)).all()
        for r in recs:
            rt = tuple([path.join(dic['resource'], _dir_, r[0].filename), r[1].page_number])
            if rt in results:
                results[rt] += 1
            else:
                results[rt] = 1

    session.close()

    if len(results) == 0:
        print('No Results are found in the database for this directory.')
        print('Go back and try updating the database instead.')
        return []

    sorted_results = []
    for val in range(max(results.values()), 0, -1):
        sorted_results += [k for k, v in results.items() if v == val]

    if len(sorted_results) > 0:
        print('Fetched {} results. '
              .format(len(sorted_results)))
        print('Type "next [x]" to view next x results. (default x=1)'
              '\nType "back" to go back for a new search.')

    return sorted_results


def delete_record(dir_name, file_name):
    session.begin()
    recs = session.query(File).filter_by(dir_name=dir_name, filename=file_name).all()
    if len(recs) == 0:
        print('This file/directory doesn\'t exist in database.')
        return
    for r in recs:
        serials = session.query(Record).filter_by(serial=r.serial).all()
        for s in serials:
            session.delete(s)
        session.delete(r)
        session.commit()
    session.close()
    print(path.join(dic['resource'], dir_name, file_name, ' successfully deleted.'))


def update_database(sub_dir):
    files = glob(path.join(dic['resource'], sub_dir, '*.pdf'))
    session.begin()
    for file in files:
        f_name = path.relpath(file, path.join(dic['resource'], sub_dir))
        r = session.query(File).filter_by(filename=f_name).first()
        if r is None:
            print('Extracting data from {}'.format(f_name))
            f = File(dir_name=sub_dir, filename=f_name)
            session.add(f)
            session.flush()
            if not os.path.exists('temp'):
                os.mkdir('temp')
            pages = convert_from_path(file, poppler_path=dic['poppler'], output_folder='temp')
            n = len(pages)
            for number, page in enumerate(pages, start=1):
                print('Processing {} out of {} pages'.format(number, n), end='\r')
                text = str((pytesseract.image_to_string(page)))
                rec = Record(serial=f.serial,
                             page_number=number,
                             content=text)
                session.add(rec)
                session.commit()
            print('Finished processing {} successfully.'.format(file))
            del pages
            shutil.rmtree('temp')
    print('The directory "{}" is up to date.'.format(sub_dir))
    session.close()


def get_prompt():
    st = '\n' + prompts[0] + d
    if len(prompts) > 1:
        for it in prompts[1:]:
            st += it + d
    return st + d + ' '


def exit_search():
    global curr_res, res, prompts
    curr_res = 0
    res.clear()
    prompts.pop()
    print('Current search terminated')


def print_dir():
    print('Resource Directory: ', dic['resource'])
    print('-------------- Directories Available --------------')
    for ind in index:
        print('\t', ind.title())
    print('---------------------------------------------------')
    print('Usage: search DIRECTORY_NAME')
    print('Usage: update DIRECTORY_NAME')
    print('Usage: delete DIRECTORY_NAME')
    print('Usage: setpath')


# Starting Main
print_dir()
while command != 'exit':
    command = input(get_prompt()).lower()
    level = len(prompts)
    if command == 'exit':
        continue
    elif command == 'back':
        if len(prompts) > 1 and level != 3:
            prompts.pop()
        elif level == 3:
            exit_search()
        continue
    elif command == 'setpath':
        if level != 1:
            print('Go back to index for setpath')
        else:
            print('Options: ', args)
            p_ = input(d + d + ' ').lower()
            if p_ not in args:
                print('Incorrect command. Try again.')
            else:
                set_path(p_)
                print_dir()
        continue
    if level == 1:
        cs = command.lower().split(' ')
        if len(cs) == 1:
            print('Undefined command. See usage')
            continue
        else:
            cs = [cs[0], ' '.join(cs[1:])]

        if cs[0] not in ['search', 'update', 'delete'] or cs[1] not in index:
            print('Undefined command. See usage')
            if cs[1] not in index and cs[0] in ['search', 'update', 'delete']:
                print('Invalid directory name: ', cs[1])
            continue

        if cs[0] == 'search':
            s_name = cs[1].title()
            _dir_ = cs[1]
            session.begin()
            test_dir_exist = session.query(File).filter_by(dir_name=cs[1]).first()
            session.close()
            if test_dir_exist is None:
                print('This directory is not present in database.')
                print('Try updating the database with this directory name instead.')
            else:
                prompts.append(s_name)
                print('To search the database enter the relevant keywords delimited by comma(,)'
                      ' without any space around it.')
        elif cs[0] == 'update':
            update_database(cs[1])
        elif cs[0] == 'delete':
            p_ = input('Enter filename' + d + d + ' ')
            if os.path.exists(path.join(dic['resource'], cs[1], p_)):
                delete_record(cs[1], p_)
            else:
                print('File doesn\'t exist!')
        continue
    elif level == 2:
        res = search_database(command)
        if len(res) > 0:
            prompts.append('Search Results')
        continue
    elif level == 3:
        cs = command.split(' ')
        n_res = 1
        if len(cs) > 2 or cs[0] != 'next':
            print('Usage: next [x]')
            continue
        elif len(cs) == 2 and not cs[1].isdigit():
            print('Usage: next [x]')
            continue
        else:
            if len(cs) == 2:
                n_res = int(cs[1])
            for i in range(n_res):
                if curr_res < len(res):
                    subprocess.Popen([dic['acrobat'], '/n', '/A',
                                      'page={}'.format(res[curr_res][1]),
                                      res[curr_res][0]],
                                     shell=False, stdout=subprocess.PIPE)
                    curr_res += 1
                    if curr_res == len(res):
                        print('All results have been displayed for current search.')
                        exit_search()
                        break
                else:
                    print('All results have been displayed for current search.')
                    exit_search()
                    break
