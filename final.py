import sqlite3, re, os, ast, time, uuid, json, random, pyadb3
from datetime import datetime
import strip_non_ascii

calibre_directory = 'D:\\Documents\\calibre\\'
nook_drive_letter = 'E:\\'
nook_sd_card_letter = None
calibre_highlight_color = 'yellow' #change to one of the other builtin calibre highlight colors if you want to use a different color to distinguish annotaitons that originated on nook


def timestamp_to_nook_string(timestamp, newer_firmware):
    if newer_firmware:
        return datetime.strftime(timestamp, '%#m/%#d/%Y %#I:%M %p')
    else:
        return datetime.strftime(timestamp, '%m/%d/%y, %#I:%M %p')


def timestamp_to_calibre_string(timestamp):
    return datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')


def nook_string_to_timestamp(stringg, newer_firmware):
    stringg = re.sub(r'([^0-9]|^)(\d[^0-9])', r'\g<1>0\2', stringg)
    if newer_firmware:
        return datetime.strptime(stringg, '%m/%d/%Y %I:%M %p')
    else:
        return datetime.strptime(stringg, '%m/%d/%y, %I:%M %p')


def calibre_string_to_timestamp(stringg):
    return datetime.strftime(stringg, '%Y-%m-%dT%H:%M:%S.%fZ')


def convert_nook_cfi_to_calibre(cfi):
    num_new = int(re.findall(r'#point\(/(\d+)', cfi)[0]) + 1
    cfi = re.sub(r'(#point\(/)\d+', r'\g<1>' + str(num_new), cfi)
    return cfi


def convert_calibre_cfi_to_nook(cfi):
    num_new = int(re.findall(r'#point\(/(\d+)', cfi)[0]) - 1
    cfi = re.sub(r'(#point\(/)\d+', r'\g<1>' + str(num_new), cfi)
    return cfi


def extract_spine(cfi):
    return re.findall(r'(.+)#', cfi)[0]


def strip_spine(cfi):
    return re.findall(r'point\((.+)\)', cfi)[0]


def strip_punctuation(sstring):
    for character in [':', ',', '.', '\"', "\'", '/', '?', ';', '(', ')', '!', '#', '&', '%', '=', '-', '_', '+']:
        if character in sstring:
            sstring=sstring.replace(character, '')
    return sstring


def check_if_file_new(fp):
    try:created = os.stat(fp).st_ctime
    except FileNotFoundError: return False
    now = datetime.timestamp(datetime.now())
    if (now-created)<5: return True
    else: return False


def check_firmware():
    print('checking nook firmware version...')
    adb = pyadb3.ADB(adb_path='./adb/adb.exe')
    adb.get_remote_file('data/data/com.bn.devicemanager/databases/devicemanager.db', './')
    if not check_if_file_new('./devicemanager.db'):
        print('seem to have failed to pull file from nook, check usb connection and such')
        exit(1)
    connection = sqlite3.connect('./devicemanager.db')
    cursor = connection.cursor()
    cursor.execute("select value from registry where name='com.bn.device.system.software_version'")
    version = cursor.fetchall()[0][0]
    if version[2] == '1':
        #older version
        return False
    else:
        #newer version
        return True


def process_nook_dir(dirr):
    alll = []
    for root, dirs, files in os.walk(dirr, topdown=True):
        for name in files:
            if name[len(name) - 5:len(name)] == '.epub':
                matches = re.findall(r'(.+) - (.+)\.epub', name)
                if matches == []:
                    continue
                else:
                    matches = matches[0]
                new_name = matches[0]
                if new_name[len(new_name) - 3:len(new_name)] == ', A':
                    new_name = 'A ' + name[:len(new_name) - 3]
                elif new_name[len(new_name) - 4:len(new_name)] == ', An':
                    new_name = 'An ' + name[:len(new_name) - 4]
                elif new_name[len(new_name) - 5:len(new_name)] == ', The':
                    new_name = 'The ' + new_name[:len(new_name) - 5]
                #convert file path
                fp = os.path.join(root, name)
                fp = fp.replace(dirr, 'file:///media/')
                fp = fp.replace('\\', '/')
                alll.append((strip_punctuation(new_name), fp))
                #print alll
    if alll == []: print('no matching epubs found in drive '+dirr+', check the variable')
    return alll


def get_nook_documents():
    print('getting list of nook ebooks...')
    alll = []
    if nook_sd_card_letter:
        alll+=(process_nook_dir(nook_sd_card_letter))
    alll+=(process_nook_dir(nook_drive_letter))
    return alll


def get_nook_annotations():
    print('getting nook annotations..')
    adb = pyadb3.ADB(adb_path='./adb/adb.exe')
    adb.get_remote_file('/data/data/com.bn.nook.reader.activities/databases/annotations.db', './')
    if not check_if_file_new('./annotations.db'):
        print('seem to have failed to pull file from nook, check usb connection and such')
        exit(1)
    connection = sqlite3.connect('./annotations.db')
    cursor = connection.cursor()
    cursor.execute("""SELECT * FROM annotations;""")
    results = cursor.fetchall()
    luids = [row[2] for row in results]
    connection.close()
    results_edited = []
    for result in results:
        result = list(result)
        document = result[1]
        document_string = re.findall(r'/([^/]+)\..+$', str(document))
        if not document_string:
            #print('error on document: ', document, 'probabyl not a calibre-generated document')
            continue
        document_string = document_string[0]
        document_title = strip_punctuation(re.findall(r'([^-]+) -', document_string)[0])
        result.append(document_title)

        # for column in result:
        #     if type(column)== str or type(column)==unicode:
        #         result[result.index(column)] = column.encode('UTF-8')

        results_edited.append(result)
    #print results_edited
    return results_edited,luids


def get_calibre_data():
    print('getting calibre data...')
    connection = sqlite3.connect(calibre_directory+'metadata.db')
    cursor = connection.cursor()
    cursor.execute('select * from books')
    books = cursor.fetchall()
    cursor.execute('select * from annotations')
    annotations = cursor.fetchall()
    connection.close()

    books_edited = []
    for row in books:
        row_list = list(row)
        row_list[1] = strip_punctuation(strip_non_ascii.strip_non_ascii(row_list[1]))
        books_edited.append(row_list)

    annotations_edited = []

    for row in annotations:
        try:
            row_dict = ast.literal_eval(row[8])
        except ValueError:
            continue
        if 'removed' in row_dict: continue
        if row_dict['type'] == 'bookmark':continue
        else:
            annotations_edited.append(list(row))
    return books_edited, annotations_edited


def find_matching_docs(calibre_books, nook_docs):
    #matched_count = 0
    #not_matched = []
    matched = []

    for doc in nook_docs:
        if doc[0] in [row[1] for row in calibre_books]:
            #matched_count +=1
            matching_book_id = next(row[0] for row in calibre_books if row[1]==doc[0])
            matched.append((matching_book_id, doc[1]))
        #else:
            #not_matched.append(doc[0])
    #print('found '+str(matched_count)+' out of '+str(len(nook_docs))+' nook documents in calibre')
    #print('nook documents that were not found in calibre: '+ str(not_matched))
    return matched


def remove_annotation_conflicts(calibre_annotations, nook_annotations): #todo: rewrite in general to be simpler
    calibre_start_cfis = [(ast.literal_eval(row[8])['start_cfi'], row) for row in calibre_annotations]
    calibre_end_cfis = [(ast.literal_eval(row[8])['end_cfi'], row) for row in calibre_annotations]
    #todo: these don't both have to be tuples actually
    calibre_just_start_cfis = [tupple[0] for tupple in calibre_start_cfis]
    calibre_just_end_cfis = [tupple[0] for tupple in calibre_end_cfis]
    duplicates = 0

    for annotation in list(nook_annotations):
        annotation_start_converted = convert_nook_cfi_to_calibre(annotation[5])
        annotation_start_converted = strip_spine(annotation_start_converted)
        if annotation_start_converted in calibre_just_start_cfis:
            #potential conflict, check the end as well
            annotation_end_converted = convert_nook_cfi_to_calibre(annotation[6])
            annotation_end_converted = strip_spine(annotation_end_converted)
            if annotation_end_converted in calibre_just_end_cfis:
                #todo eventually: compare timestamps
                matching_row_index = next(calibre_annotations.index(row) for row in calibre_annotations if (ast.literal_eval(row[8])['start_cfi']==annotation_start_converted) and (ast.literal_eval(row[8])['end_cfi']==annotation_end_converted))
                calibre_annotations.pop(matching_row_index)

                matching_row_index = nook_annotations.index(annotation)
                nook_annotations.pop(matching_row_index)
                duplicates+=1
    print(str(duplicates)+' previously synchronized or duplicate annotations skipped')
    return calibre_annotations, nook_annotations


def nook_annotations_to_calibre(nook_annotations, newer_firmware, matching_docs):
    if nook_annotations==[]:return
    print('copying nook annotations to calibre...')
    sql_entries = []
    for annotation in nook_annotations:
        spine = extract_spine(annotation[5])
        start = strip_spine(convert_nook_cfi_to_calibre(annotation[5]))
        end = strip_spine(convert_nook_cfi_to_calibre(annotation[6]))
        timestamp = nook_string_to_timestamp(annotation[10], newer_firmware)
        timestamp_secs = float(time.mktime(timestamp.utctimetuple())  + timestamp.microsecond / 1000)
        timestamp_str = timestamp_to_calibre_string(timestamp)
        annot_id = str(uuid.uuid4())
        toc_titles = 'Unknown chapter' #todo: implement
        if annotation[7]:
            note = annotation[7]
            searchable_text = annotation[8] + ' ' + note
            data_dict = {"end_cfi": end, "highlighted_text": annotation[8], "notes": annotation[7], "spine_index": 0, "spine_name": spine, "start_cfi": start, "style": {"kind": "color", "type": "builtin", "which": calibre_highlight_color}, "timestamp": timestamp_str, "toc_family_titles": [toc_titles], "type": "highlight", "uuid": annot_id}

        else:
            searchable_text = annotation[8]
            data_dict = {"end_cfi": end, "highlighted_text": annotation[8], "spine_index": 0, "spine_name": spine, "start_cfi": start, "style": {"kind": "color", "type": "builtin", "which": calibre_highlight_color}, "timestamp": timestamp_str, "toc_family_titles": [toc_titles], "type": "highlight", "uuid": annot_id}

        book_id = next(tupple[0] for tupple in matching_docs if tupple[1]==annotation[1])
        sql_entries.append((book_id, 'EPUB', 'local', 'viewer', timestamp_secs, annot_id, 'highlight', json.dumps(data_dict), searchable_text))
    connection = sqlite3.connect(calibre_directory+'metadata.db')
    cursor = connection.cursor()
    sql = "INSERT INTO annotations (book, format, user_type, user, timestamp, annot_id, annot_type, annot_data, searchable_text) VALUES (?,?,?,?,?,?,?,?,?)"
    cursor.executemany(sql, sql_entries)
    connection.commit()
    connection.close()


def calibre_annotations_to_nook(calibre_annotations, newer_firmware, matching_docs, luids):
    if calibre_annotations == []:return
    print('copying calibre annotations to nook...')
    sql_entries = []
    for annotation in calibre_annotations:
        annotation_dict = ast.literal_eval(annotation[8])

        matching_file = next(tupple[1] for tupple in matching_docs if tupple[0]==annotation[1])

        nook_timestamp = timestamp_to_nook_string(datetime.fromtimestamp(annotation[5]), newer_firmware)
        nook_ms = int(annotation[5]*1000)

        spine = annotation_dict['spine_name']
        start = convert_calibre_cfi_to_nook(spine+'#point('+annotation_dict['start_cfi']+')')
        end = convert_calibre_cfi_to_nook(spine+'#point('+annotation_dict['end_cfi']+')')

        pagenumber = 0 #todo: implement if possible (idk how the nook determines page numbers)

        if newer_firmware: color = '0x8be58f'
        else: color = '0xbbbbbb'

        #todo: improve
        while True:
            luid = random.randrange(0,999999999999999999) #i don't actually know what the max size is
            if luid not in luids:
                break

        try:
            notes = annotation_dict['notes']
            has_note = 1
        except KeyError:
            notes = None
            has_note = 0

        sql_entries.append((matching_file, luid, nook_ms, 1, start, end, notes, annotation_dict['highlighted_text'], pagenumber, nook_timestamp, has_note, 1, color, 1))
    connection = sqlite3.connect('./annotations.db')
    connection.text_factory = str
    cursor = connection.cursor()
    sql = "INSERT INTO annotations (ean, luid, lastupdated, bookdna, startlocation, enlocation, note, highlighttext, pagenumber, timestamp, hasNote, ishighlighted, color, sync_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    cursor.executemany(sql, sql_entries)
    connection.commit()
    connection.close()
    adb = pyadb3.ADB(adb_path='./adb/adb.exe')
    adb.push_local_file('./annotations.db', '/data/data/com.bn.nook.reader.activities/databases/annotations.db')
    #todo: how to check that this happened successfully?
    print('finished copying calibre annotations to nook, please eject nook and reboot it fully')


def synchronise_annotations():
    calibre_data = get_calibre_data()
    calibre_books = calibre_data[0]
    calibre_annotations = calibre_data[1]
    newer_firmware = check_firmware()

    nook_docs = get_nook_documents()
    nook_annotations, annotation_luids = get_nook_annotations()

    matching_docs = find_matching_docs(calibre_books, nook_docs)
    print(str(len(matching_docs))+' documents found in both calibre and nook')

    # discard the annotations that are not attached to books that exist in both calibre and nook
    calibre_annotations = [annotation for annotation in calibre_annotations if annotation[1] in [doc[0] for doc in matching_docs]]
    nook_annotations = [annotation for annotation in nook_annotations if annotation[1] in [doc[1] for doc in matching_docs]]
    print(str(len(calibre_annotations))+ ' relevant calibre annotations found')
    print(str(len(nook_annotations))+ ' relevant nook annotations found')

    calibre_annotations, nook_annotations = remove_annotation_conflicts(calibre_annotations, nook_annotations)

    nook_annotations_to_calibre(nook_annotations, newer_firmware, matching_docs)
    calibre_annotations_to_nook(calibre_annotations, newer_firmware, matching_docs, annotation_luids)


# if name main...
synchronise_annotations()
