import re
from typing import Optional
import lzstring
import prison
from urllib.parse import quote_plus
import sys
import os
from tlh import settings

CEXPLORE_URL='https://cexplore.henny022.eu.ngrok.io/#'
#CEXPLORE_URL='http://localhost:10240/#'

def rison_quote(text: str) -> str:
    return quote_plus(text).replace('%2C', ',').replace('%3A', ':').replace('%40', '@').replace('%24', '$').replace('%2F', '/').replace('%20', '+')

def risonify(data) -> str:
    return rison_quote(prison.dumps(data)[1:-1])

def generate_cexplore_url(src: str, asm: str) -> str:
    # Base state url
    # state = 'OYLghAFBqd5QCxAYwPYBMCmBRdBLAF1QCcAaPECAM1QDsCBlZAQwBtMQBGAZlICsupVs1qgA+hOSkAzpnbICeOpUy10AYVSsArgFtaIAEwAGUqvQAZPLUwA5PQCNMxEADZSAB1TTCS2pp19I1MvH0U6Kxt7XScXd1l5cNoGAmZiAgC9AxMZOUwFPxS0gki7R2c3GVT0zKCc6WqS6zKYitcAShlUbWJkDgByAFJDbmtkHSwAamHDVUUCAE8AOgQZweMAQWHR2nHtKZmqbV2k6RW1ze2xicxpw0MPYQXnc/v1rZHr/duZ6WRiPAeAivQzvd4AenBkw26HQk3UkzQUwQzlu/U6rBA/QArP1SAZ+sY8agsQjpN1ej8Rpw8QQsUTOhAkGhdB48OwyBQICy2RyQARdMgxMxgA5kFIqOyCM5pJQHPS8Q5rGkFliaaQWbo5gB5WisVWEvFYXQiYDsBWkfDEfKKABumFlhrMAA98tppWq8dZpZinaw8A5iCrNFhPaQCADdJ7OjR6Ew2BxOAAWfiCYSiEASMRSf0OWWQTqoIF+R14hI2vwqNS1AycMxqUrRWKCUK+Og1lveNu0RvlFx18sFOhFGpaLKCQdJEdNKJ9ieNDsDxq91r9zrknp9LgYrG4/EWkn9AVCkVi5CTCC4QgkO7cOvw1Cs9nOW+cdrw2kK9qdADWIG4xhLJwrjcNwAAchggUmADsJjYtiQhYkmeJRpwximASRKkIeZYgKYdKGoyMBQMRTIgPgVBUOQlCxowLDmpwdasAgspMSxFFUIsHgcKYxAsUYpB8dIHFcTxO44nimHEliAAieCUZMx7CqK4qTLa0iIswBCfoRnQoswWAuBAv4gEm3BLDB3BmcYrjQQAnA5xhgUxSEoSA0HQUs3DQQBrhgWZkHQWhYH7k6OEyHh4ZfqQcCwEg3QEB47rUdyj68hUdaYPgRD9qQtHxgxdYAO5Bh40aIRJoVYYe2ycJMRWEAgimCspZ46QyemYAZFTGRVyGkFG9xLK4kF2Xe2K2dwhhgXZhgplJ2FYrh+FfiZSbYksM1JjwjHbR5SbGAhvrcJJB5LVFhExaRzIYDg2UkCl+X0YmvACIYQimiAzDSLIMT6rkiSVhA5gdoYCHmCuzZ1q2SSgwhMN+JDGUAxWw4LmOdQIZOhTLs0TbIw0xRw1UxRI2uXSbgMAAC0KwpM32/Q4+qIrdkwota6IVXuC2HhsP2YH9CyTBulK3oY7Wc2RPLPpylDS3yHgLCwBB5VKMpyhaSq0CqYaajqeoGlhxqmuaTpWhW9qOlhmCusg7oDOq3pyBauZBsQCwhgMWERngUb9DSMZ0HRCZcCmb0fRmDMC0zCxCAG+a9UWpzndjyjA9WGO1vWlh43O0NdrDmedmEiO56uE55EOyTo4EWep9XpNl1DJOjrX86N7O5dvhTlJGOJ3Nnf0ysXleOVi6QD5PhyYvvnzjP6hL36kH+IxLHZSZzWBI0jNih3bX1p1hSnkUER1FXi1V0n9IvnT2sQPjKEmQA'

    # state = lzstring.LZString().decompressFromBase64(state)
    # print(state)
    state = "g:!((g:!((g:!((h:codeEditor,i:(fontScale:13,j:1,lang:___c,selection:(endColumn:20,endLineNumber:6,positionColumn:20,positionLineNumber:6,selectionStartColumn:20,selectionStartLineNumber:6,startColumn:20,startLineNumber:6),source:'%23include+%22entity.h%22%0A%23include+%22functions.h%22%0A%23include+%22player.h%22%0A%23include+%22script.h%22%0A%0A//+Add+C+code+here+'),l:'5',n:'0',o:'C+source+%231',t:'0'),(h:compiler,i:(compiler:tmc_agbcc,filters:(b:'0',binary:'1',commentOnly:'0',demangle:'0',directives:'0',execute:'1',intel:'0',libraryCode:'1',trim:'1'),fontScale:14,j:1,lang:___c,libs:!(),options:'-O2',selection:(endColumn:1,endLineNumber:1,positionColumn:1,positionLineNumber:1,selectionStartColumn:1,selectionStartLineNumber:1,startColumn:1,startLineNumber:1),source:1),l:'5',n:'0',o:'tmc_agbcc+(Editor+%231,+Compiler+%231)+C',t:'0')),k:30.16338263472055,l:'4',m:100,n:'0',o:'',s:0,t:'0'),(g:!((g:!((h:diff,i:(fontScale:11,lhs:1,lhsdifftype:0,rhs:2,rhsdifftype:0),l:'5',n:'0',o:'Diff+tmc_agbcc+vs+cat',t:'0')),header:(),k:43.47343067999081,l:'4',m:77.37306843267108,n:'0',o:'',s:0,t:'0'),(g:!((h:output,i:(compiler:1,editor:1,fontScale:11,wrap:'1'),l:'5',n:'0',o:'%231+with+tmc_agbcc',t:'0')),header:(),l:'4',m:22.626931567328924,n:'0',o:'',s:0,t:'0')),k:45.89413114177405,l:'3',n:'0',o:'',t:'0'),(g:!((h:codeEditor,i:(fontScale:13,j:2,lang:assembly,selection:(endColumn:25,endLineNumber:1,positionColumn:25,positionLineNumber:1,selectionStartColumn:25,selectionStartLineNumber:1,startColumn:25,startLineNumber:1),source:'@+Add+assembly+code+here'),l:'5',n:'0',o:'Assembly+source+%232',t:'0'),(h:compiler,i:(compiler:pycat,filters:(b:'0',binary:'1',commentOnly:'0',demangle:'0',directives:'0',execute:'1',intel:'0',libraryCode:'0',trim:'1'),fontScale:14,j:2,lang:assembly,libs:!(),options:'',selection:(endColumn:1,endLineNumber:1,positionColumn:1,positionLineNumber:1,selectionStartColumn:1,selectionStartLineNumber:1,startColumn:1,startLineNumber:1),source:2),l:'5',n:'0',o:'cat+(Editor+%232,+Compiler+%232)+Assembly',t:'0')),k:23.94248622350541,l:'4',n:'0',o:'',s:0,t:'0')),l:'2',n:'0',o:'',t:'0')),version:4"
    data = prison.loads('(' + state + ')')


    # Insert our code in the editors
    data['g'][0]['g'][0]['g'][0]['i']['source'] = src
    data['g'][0]['g'][2]['g'][0]['i']['source'] = asm

    state = risonify(data)
    state = {
        'z': lzstring.LZString().compressToBase64(state)
    }
    url = (CEXPLORE_URL+risonify(state))
    return url
