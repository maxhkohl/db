
#import pandas.io.data as p
import pymongo
import urllib
import urllib2
import datetime
import sys
import pytz
from PyQt4 import QtCore, QtGui, uic


#Load UI
form_class = uic.loadUiType("ui.ui")[0]

class MyWindowClass(QtGui.QMainWindow, form_class):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.build.clicked.connect(self.build_it)
        self.avgVolBtn.clicked.connect(self.getAvgVol)

    def getAvgVol(self,database):
        """query = []
        lastMonth = 12
        lastDay = 21
        monthsPerYear = 12
        symbol = self.avgVolSym.text()
        start = self.avgVolStart.date()
        end = self.avgVolEnd.date()
        startYear = int(start[0])
        startMonth = int(start[1])
        startDay = int(start[2])
        endYear = int(end[0])
        endMonth = int(end[1])
        endDay = int(end[2])
        if startYear != endYear:
            years = startYear = endYear
            if years >= 2:
                for year in years:
                    query.append(database.find({"Symbol":symbol,"Year":{"$gt":(startYear+1),"$lt":(endYear-1)}}))
            else:
                for month in range(monthsPerYear-startMonth):"""



        #Debugging purposes
        print str(start) + "\t" + str(end) + "\t"

    def build_it(self):
        self.outputBox.clear()
        valid = True
        s = str(self.symbolBox.text())
        if s.isalpha() == False:
            self.outputBox.append("The symbol is invalid")
            valid = False
        i = str(self.intervalBox.text())
        if i.isdigit() == False:
            self.outputBox.append("The time interval is invalid")
            valid = False
        p = str(self.periodBox.text())
        if p.isdigit() == False:
            self.outputBox.append("The time period is invalid")
            valid = False
        if valid == True:
            self.outputBox.append("Processing...")
            self.database = connectDB()
            #print "Database Connected\n"
            output = useGoogle(self.database, s, int(i), int(p))
            #print collection
            numEntries = output[1]
            self.collection = output[0]
            self.outputBox.append("Added " + str(numEntries) + " entries successfully.")

def connectDB():
    try:
        db = pymongo.MongoClient()
        return db
    except:
        print "Failed miserably"

def connectCollection(db,collName):
    database = db.masterDB
    collection = collName
    dbc = database[collection]
    return dbc

def getURL(symbol,ts,ti):

    #Encode the URL data
    urldata = {}
    urldata['q'] = symbol           # stock symbol
    urldata['i'] = str(ts)   # interval
    urldata['p'] = ti     # number of past trading days (max has been 15d)
    urldata['f'] = 'd,o,h,l,c,v'    # requested data d is time, o is open, c is closing, h is high, l is low, v is volume
    url_values = urllib.urlencode(urldata)          #Encode URL parameters
    url = 'http://www.google.com/finance/getprices' #Base URL
    url = url + '?' + url_values               #Concatenate base URL and encoded parameters
    return url

def getWebData(url):
    req = urllib2.Request(url)                 #Ask nicely for Google data
    return urllib2.urlopen(req).readlines()     #Get...the data

def getExchange(header):
    index = header.find("%")+3
    exchange = header[index:]
    exchange = exchange.rstrip()
    return exchange

def cleanLine(line):
    line = line.rstrip()        #Strip off newline characters
    line = line.split(",")      #Split at commas (CSV format)
    return line

def getTime(line, timeSlice, baseTime):
    #Examine the timestamp
    #An a in front of the timestamp indicates it is a new day
    if 'a' in line[0]:
        line[0] = line[0].strip('a')    #Take the a off the front
        baseTime = int(line[0])         #This time is the beginning of a new day
        time = datetime.datetime.fromtimestamp(baseTime)    #Set the time and date object based on this timestamp
        #Otherwise, the time stamp is an offset from the base time stamp
    else:
        #print(line[0])
        deltaTime = timeSlice * int(line[0])    #Time offset
        time = datetime.datetime.fromtimestamp(baseTime+deltaTime)  #Add time offset to the base time
    return time, baseTime

def useGoogle(db,symbol, ts, ti):
    #Variable instantiation
    baseTime = 0
    cumulativeV = 0
    cumulativeVP = 0
    prevDay = 0
    collectionName = "Stock-History"

    #Sanitize input
    stock = symbol.upper() #'JPM'
    #print stock
    timeInterval = str(ti) + 'd' #Add the d character for Google's URL
    #print timeInterval
    timeSlice = ts * 60 #Convert time slice into seconds
    #Web stuff
    url = getURL(stock,timeSlice,timeInterval)
    print url
    data = getWebData(url)

    header = data[0:7]   #Save header for future use
    del data[0:7]   #Leaving the header attached could mess things up

    exchange = getExchange(header[0])

    #Connect to (and create) a DB with a collection name defined above
    collection = connectCollection(db,collectionName)

    #Iterate through the returned entries
    counter = 0
    #print(len(data))
    for line in data:
        #Remove junk from input
        line = cleanLine(line)

        #Get time info, getTime returns a tuple of time and baseTime
        if "OFFSET" in line[0]:
            continue
        time = getTime(line, timeSlice, baseTime)
        baseTime = (time[1])
        time = time[0]

        #Separate date and time
        date = time.strftime('%Y-%m-%d')    #Year-Month-Day
        line.insert(0,date)                 #Insert date at the beginning of list
        time = time.strftime('%H:%M:%S')    #Hours:Mins:Seconds
        line[1] = time                      #Replace now useless time stamp with time

        #Add in stock and exchange data at beginning
        line.insert(0,exchange)
        line.insert(0,stock)

        #Convert Open, High, Low, Close and Volume from string to float for future use
        for i in range(4,len(line)):
            line[i] = float(line[i])

        volume = line[8]
        if volume == 0:
            #THIS IS BECAUSE VOLUME DATA IS NOT UPDATED FOR A FEW MINUTES!
            continue
        else:
            #Separate year month and day for future searching purposes
            date = line[2].split("-")
            year = date[0]
            month = date[1]
            day = date[2]

            #Check to see if there is an identical entry in the database, DONT ENTER IT IF THERE IS A MATCH!
            if (len(list(collection.find({"Time":line[3],"Year":year,"Month":month,"Day":day,"Symbol":line[0]})))) == 0:
                #Find average price over time interval
                high = line[5]
                low = line[6]
                close = line[4]
                avg = (high + low + close)/3
                #Add it to the end of list
                #VWAP calculation
                #Start with volume price (average price, that is)
                vp = volume*avg
                if prevDay == day:
                    #Add volume to cumulative volume
                    cumulativeV += volume
                    cumulativeVP += vp
                else:
                    #It is a new day, start fresh
                    cumulativeV = volume
                    cumulativeVP = vp
                    prevDay = day
                #Find VWAP (price * volume) / Cumulative volume
                vwap = cumulativeVP/cumulativeV
                print str(cumulativeV) + "\t" + str(cumulativeVP) + "\t" + str(avg) + "\t" + str(vwap)

                #Put it in a dictionary for Mongo use
                doc = {"Symbol":line[0],"Exchange":line[1],"Year":year,"Month":month,"Day":day,"Time":line[3],"Close":close,"High":high,"Low":low,"Open":line[7],"Volume":volume,"Average":avg, "VWAP":vwap}
                collection.insert(doc)
                #print "Added:\t" + line[0] + " time:\t" + line[3] + "\n"
                counter = counter + 1
            #print(doc)
    return (collection, counter)

def getData(collection):
    data = list(collection.find())
    for entry in data:
        print(entry)

def useYahoo(symbol, ts, ti):

    url = 'http://chartapi.finance.yahoo.com/instrument/'
    # http://chartapi.finance.yahoo.com/instrument/1.0/GOOG/chartdata;type=quote;range=1d/csv
    url += str(float(ts))
    url += '/' + symbol.upper()
    url += '/chartdata;type=quote;range='
    url += ti + '/csv'
    #print(url)

    response = urllib.urlopen(url)
    response = response.readlines()
    #del response[0:10]
    #header = response[0]
    #del response[0:7]
    prevTime = 0
    for line in response:
        if ':' in line:
            continue
        else:
            line = line.rstrip()
            line = line.split(',')
            if prevTime != 0:
                dt = int(line[0]) - prevTime
            else:
                dt = 0
            prevTime = int(line[0])
            ts = pytz.timezone("US/Eastern")
            ts = datetime.datetime.fromtimestamp(int(line[0]), ts)
            line.insert(0,ts.strftime('%Y-%m-%d'))
            line[1] = ts.strftime('%H:%M:%S')
            low = float(line[-3])
            high = float(line[-4])
            close = float(line[-5])
            volume = float(line[-1])
            sum = low+high+close
            avg = sum/3
            line.append(avg)
            line.append(dt)
            if dt != 0:
                line.append(avg*volume/dt)
            else:
                line.append(0)

            print line



#getData(collection)


app = QtGui.QApplication(sys.argv)
app.setStyle("plastique")
myWindow = MyWindowClass(None)
myWindow.show()
app.exec_()