#!/usr/local/bin/python3.7
#
# Copyright (c) 2020 Marcel Kaiser. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from subprocess import Popen, PIPE
from os import listdir
from os.path import isfile, join
import pwd
import os, re, sys

PROGRAM			= '@PROGRAM@'
LOCALE_PATH		= '@LOCALE_PATH@'
LANG			= os.environ['LANG'].split('_')[0]
PREFIX			= '/usr/local'
PATH_APPS_DIRS  = [ 'share/applications' ]

WINDOW_TITLE = 'Set default applications'
WINDOW_WIDTH, WINDOW_HEIGHT = 300, 200

class DesktopFile:
	def __init__(self):
		self.name = None
		self.path = None
		self.icon = None

class MainWindow(QMainWindow):
	def __init__(self, *args, **kwargs):
		super(MainWindow, self).__init__(*args, **kwargs)
		container = QWidget()
		layout = QVBoxLayout(container)
		icon = QIcon.fromTheme('preferences-desktop')
		self.setWindowTitle(WINDOW_TITLE)
		self.setMinimumSize(WINDOW_WIDTH, WINDOW_HEIGHT)
		self.setWindowIcon(icon)
		self.setContentsMargins(10, 1, 10, 1)

		self.app_list = self.get_app_list()
		self.default_apps = self.get_defaults()

		self.browser_cbb = self.create_app_cbb('browser')
		self.mailer_cbb = self.create_app_cbb('mailer')
		self.fm_cbb = self.create_app_cbb('fm')
		
		form = QFormLayout()
		form.addRow(QLabel(self.tr('Default Browser:')), self.browser_cbb)
		form.addRow(QLabel(self.tr('Default Mailer:')), self.mailer_cbb)
		form.addRow(QLabel(self.tr('Default Filemanager:')), self.fm_cbb)
		layout.addLayout(form)
		
		bbox = QHBoxLayout()
		ok_bt = QPushButton(self.tr('&Ok'))
		cancel_bt = QPushButton(self.tr('&Cancel'))
		bbox.addWidget(ok_bt, 1, Qt.AlignRight)
		bbox.addWidget(cancel_bt, 0, Qt.AlignRight)

		layout.addLayout(bbox)
		self.setCentralWidget(container)

		ok_bt.clicked.connect(self.apply_changes)
		cancel_bt.clicked.connect(self.quit)

	def apply_changes(self):
		os.system("xdg-settings set default-web-browser " +
				  self.browser_cbb.currentData())
		os.system("xdg-mime default {} inode/directory" .
				  format(self.fm_cbb.currentData()))
		os.system("xdg-mime default {} x-scheme-handler/mailto" .
				  format(self.mailer_cbb.currentData()))
		self.quit()

	def quit(self):
		sys.exit(0)

	def create_app_cbb(self, key):
		n, index = 0, 0
		cbb = QComboBox()
		for f in self.app_list[key]:
			if self.default_apps[key] == f.file:
				index = n
			n = n + 1
			icon = QIcon.fromTheme(f.icon)
			cbb.addItem(icon, f.name, f.file)
		cbb.setCurrentIndex(index)
		return cbb

	def get_proc_output(self, args):
		try:
			proc = Popen(args, stdin=None, stdout=PIPE, stderr=None)
		except OSError:
			print("Failed to Popen({})".format(args))
			sys.exit(1)
		line = proc.stdout.read().replace(b'\n', b'').decode('utf-8')
		proc.wait()
		return line

	def get_defaults(self):
		mailer = self.get_proc_output(['xdg-settings', 'get',
									   'default-url-scheme-handler', 'mailto'])
		browser = self.get_proc_output(['xdg-settings', 'get',
										'default-web-browser'])
		fm = self.get_proc_output(['xdg-mime', 'query', 'default',
								   'inode/directory'])
		return {'mailer': mailer, 'browser': browser, 'fm': fm}
	
	def matches_category(self, desktopfile, category):
		rx = re.compile('^Categories=.*' + category + '.*')
		try:
			f = open(desktopfile, 'r')
		except FileNotFoundError:
			return None
		for l in f:
			m = rx.match(l)
			if m:
				f.close()
				return True
		f.close()
		return None
	
	def get_home_dir(self):
		return pwd.getpwuid(os.getuid()).pw_dir

	def read_desktopfile(self, path):
		d = DesktopFile()
		in_desktop_entry_section = None
		fallback_name = os.path.basename(path)
		if LANG and LANG != '':
			name_rx = re.compile('^Name\\[' + LANG + '\\]=(.*)$')
		fb_name_rx = re.compile('^Name=(.*)$')
		try:
			f = open(path, 'r')
		except FileNotFoundError:
			return None
		for l in f:
			if not in_desktop_entry_section:
				if l.strip('\n') == '[Desktop Entry]':
					in_desktop_entry_section = 1
				continue
			elif l.startswith('['):
				break
			if not d.name:
				m = name_rx.match(l)
				if m:
					d.name = m.group(1)
					continue
				m = fb_name_rx.match(l)
				if m:
					fallback_name = m.group(1)
					continue
			if not d.icon:
				m = re.match('^Icon=(.*)$', l)
				if m:
					d.icon = m.group(1)
		f.close()
		if not d.name:
			d.name = fallback_name
		d.path = path
		d.file = os.path.basename(path)
		return d

	def get_app_list(self):
		dirs = []
		fms = []
		mailer = []
		browser = []
		df = DesktopFile
		for d in PATH_APPS_DIRS:
			dirs.append(PREFIX + '/' + d)
		for d in PATH_APPS_DIRS:
			dirs.append(self.get_home_dir() + '/.local/' + d)
		for d in dirs:
			if not os.path.exists(d):
				continue
			for f in listdir(d):
				path = join(d, f)
				if not isfile(path):
					continue
				if self.matches_category(path, 'Email'):
					df = self.read_desktopfile(path)
					if df:
						mailer.append(df)
				elif self.matches_category(path, 'WebBrowser'):
					df = self.read_desktopfile(path)
					if df:
						browser.append(df)
				elif self.matches_category(path, 'FileManager'):
					df = self.read_desktopfile(path)
					if df:
						fms.append(df)
		return { 'mailer': mailer, 'browser': browser, 'fm': fms }

def main():
	app = QApplication(sys.argv)
	win = MainWindow()
	win.show()
	sys.exit(app.exec_())

if __name__ == '__main__':
	main()
