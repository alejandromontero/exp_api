#!/usr/bin/env ruby

# Copyright (C) 2015 NEC Corporation. NEC CONFIDENTIAL AND PROPRIETARY. 
# All rights reserved by NEC Corporation. This program must be used solely 
# for the purpose for which it was furnished by NEC Corporation. No part 
# of this program may be reproduced or disclosed to others, in any form, 
# without the prior written permission of NEC Corporation. Use of copyright 
# notice does not evidence publication of the program.

require 'rubygems'
require 'net/http'
#require 'uri'
require 'json'
require 'strscan'  # StringScanner
require 'optparse' # getopts, OptionParser::Arguable

def htonl(h)
  [h].pack("L").unpack("N")[0]
end

alias :ntohl :htonl

DestServ = Struct.new(:ip, :port, :user, :password)

def parse_ini(src)
  section = { "" => {} }
  current = section[""]
  s = StringScanner.new(src)

  while !s.eos?
    case
    when s.scan(/\s+/)
      # nothing
    when s.scan(/^[#].*$/)
      # comment
    when s.scan(/\[(.+?)\]/)
      section[s[1]] = current = {}
    when s.scan(/(\w+)\s*=\s*(["'])?([^\n]+)\2/) # unquote
      current[s[1]] = s[3]
    when s.scan(/(\w+)\s*=\s*(\S+)/)
      current[s[1]] = s[2]
    else
      raise "Parse Error. rest=#{ s.rest }"
    end
  end

  section
end

#
# MMS update-file validation check and return array
#
def mms_file_check(file)
  st = File.stat(file)
  if st.size % 4 != 0
    puts "file size is wrong. '#{file}' '#{st.size}'"
    raise ArgumentError.new "size error '#{st.size}'"
  end

  buf = ''
  File.open(file, 'rb') do |f|
    buf = f.read
  end
  a = buf.unpack("N*")
  if a[0] != 0xa5a5a5a5
    puts "magic number is wrong. '#{format("0x%x", a[0])}'"
    raise ArgumentError.new "header '#{file}' '#{format("0x%x", a[0])}'"
  end
  a
end

EEPROM_UPDFILE_HDRSZ = 16
#
# EEPROM update-file validation check and return array
#
def eeprom_file_check(file)
  st = File.stat(file)
  if st.size % 4 != 0
    puts "file size is wrong. '#{file}' '#{st.size}'"
    raise ArgumentError.new "size error '#{st.size}'"
  end

  buf = ''
  File.open(file, 'rb') do |f|
    buf = f.read
  end
  a = buf.unpack("N*")
  if st.size != ntohl(a[1]) + EEPROM_UPDFILE_HDRSZ
    puts "file header is wrong. '#{st.size}' " +
         "'#{ntohl(a[1])}(#{format("0x%08x", ntohl(a[1]))})'"
    raise ArgumentError.new "header '#{file}' '#{st.size}'"
  end
  a
end

#
# Get conf value string.
#
# @param k1 the config category
# @param k2 the config keyword
#
def conf_s(k1, k2)
  return nil if $conf.nil? || $conf[k1].nil?
  $conf[k1][k2]
end

def conf_is?(k1, k2, str)
  if $conf && $conf[k1] && $conf[k1][k2] == str
    true
  else
    false
  end
end

#
# return if validation OK or raise
#
def validate_id(id)
  if conf_is?("eemcli", "validation", "false")
    return
  end
  if /0x[\da-f]{12}$/ =~ id
    return
  end
  puts "id format error '#{id}'"
  puts "e.g. correct id format: 0x001122ddeeff"
  raise ArgumentError.new "id format error '#{id}'"
end

#
# print request method and body if verbose/debug mode
# @param req the http request object (Net::HTTPRequest)
# @param data the request body data which is json string or nil
#
def req_debug_print(req, data)
  return if !($params["v"] || $params["d"])
  puts req.method
  return if !data
  s = data
  len = 512
  puts "send: " + (s.size > len ? s[0...len] + "..." : s)
end

#
# print response code and response content
# @param response the response typed Net::HTTPResponse.
#
def resp_print(response)
  if $params["v"] || $params["d"]
    puts "HTTP response header:"
    puts response.header.to_hash
  end
  puts "#{response.code} (#{response.class})"
  return if response.content_type.nil?
  if response.content_type.start_with?('text/html')
    begin
      require 'nokogiri'
    rescue LoadError
      puts response.body
      return
    end
    doc = Nokogiri::HTML.parse(response.body, nil, 'UTF-8')
    puts doc.title
    doc.css('body')[0].children.each do |i| 
      if i.node_name != 'hr'
        s = i.to_s.chomp
        next if s.empty?
        puts s
      end
    end 
  elsif response.content_type == 'application/json'
    r = JSON.parse(response.body)
    if $params["pp"]
      puts JSON.pretty_generate(r)
    else
      puts response.body
    end
  end
  #p response
end

#
# do http request
# @param req_method the HTTP request method symbol
# @param url the URI string
# @param user the basic authentication user
# @param password the basic authentication password
# @param data the request body data which is json string or nil
# @param type the content type (optional param default json)
#
def do_http_req(req_method, url, user, password, data, type="application/json")
  uri = URI.parse(url)
  http = Net::HTTP.new(uri.host, uri.port)
  if conf_is?("eemcli", "debughttplib", "true")
    http.set_debug_output($stderr)
  end

  timeout = http.read_timeout
  do_if(conf_s("eemcli","timeout")) {|x| timeout = x.to_i}
  http.read_timeout = timeout

  req = Net::HTTP.const_get(req_method).new(uri.request_uri)
  req.basic_auth user, password if user
  req['Content-Type'] = type if data
  req['Accept'] = "application/json"
  req['Accept-Language'] = "en-US,en;q=0.8,ja;q=0.6"

  req_debug_print(req, data)
  if data
    response = http.request(req, data)
  else
    response = http.request(req)
  end
  resp_print(response)
end

#
# exec proc
# @param argv the argument
# @param user the basic authentication user
# @param password the basic authentication password
#
# e.g.
# PUT http://localhost:8080/foo/bar -j baz.json
#
def exec_case_proc(argv, user, password)
  arg = argv.dup

  req_method = arg[0].downcase.capitalize.to_sym
  begin
    Net::HTTP.const_get(req_method)
  rescue NameError => e
    puts "Method error (#{e.class}) '#{ARGV.join(" ")}'"
    raise ArgumentError.new "method error '#{arg[0]}'"
  end
  url = arg[1]
  arg.shift
  arg.shift

  data = nil
  type = nil
  if req_method == :Get && arg.size == 0
    arg.push('-j', '/dev/null')
  end
  case arg[0]
  when '-j'
    buf = nil
    File.open(arg[1], 'rb') do |f|
      buf = f.read
    end
    begin
      JSON.parse(buf)
    rescue JSON::ParserError
      if File.executable?(arg[1])
        puts "Executable! size=#{buf.size} '#{ARGV.join(" ")}'"
        raise ArgumentError.new "executable file not permitted '#{arg[1]}'"
      end
      type = "text/plain"
    end
    data = buf
  when '-e'
    arg.shift
    if !File.executable?(arg[0])
      puts "Not executable '#{ARGV.join(" ")}'"
      raise ArgumentError.new "file not executable '#{arg[0]}'"
    end
    cmd = arg.join(' ')
    buf = `#{cmd}`
    if buf.chomp.empty?
      data = nil
    else
      data = buf # buf.chomp
    end
  else
    puts "No such option '#{ARGV.join(" ")}'"
    raise ArgumentError.new "no such option '#{arg[0]}'"
  end

  if type
    do_http_req(req_method, url, user, password, data, type)
  else
    do_http_req(req_method, url, user, password, data)
  end

end

#
# check parameter and return id and array.
# raise if error.
# @param params the params created by argv.getopts.
# @param argv the rest argument above.
# @param f the method to call. does not call if nil.
#
def param_check(params, argv, f)

  return [nil, nil] if !f
    
  id = params["i"] || params["id"]

  validate_id(id)

  if argv.size == 0
    puts "Not specified update file '#{ARGV.join(" ")}'"
    raise ArgumentError.new "file not specified"
  end

  file = argv.shift
  a = f.call(file)

  [id, a]
end

#
# Common/general one request and print response.
#
def one_request(ds, rsc, id, a)
  if a
    data = {'data'=> a.map{|x| format("0x%x", x)}, "id"=> id}
    req_method = :Put
  else
    data = nil
    req_method = :Get
  end

  url = "http://#{ds.ip}:#{ds.port}/eem/#{rsc}"

  do_http_req(req_method, url, ds.user, ds.password, 
              (data ? data.to_json : nil))
end

require_relative 'm/cli-rest'

#
# print usage.
#
def usage
  prog = File.basename($0)
  print <<"E"
Usage: #{prog} [-h] <subcommand> ...

Positional arguments:
  <subcommand>
    eeprom_update       EEPROM update-file request.
    mms_update          MMS update-file request.
    devices             List all device IDs.
    exec                Exec general http request method.
    do                  Same as above. 'exec' alias.
    ls                  'ls' command. List devices/groups.

Subcommand syntax required input file arguments:
    eeprom_update --id <id> <eeprom_update_file>
    mms_update    --id <id> <mms_update_file>

Subcommand 'exec' command syntax:
    exec <http_method> <URI> -j <input_json_file>
    exec <http_method> <URI> -e <json_generate_script>

    e.g.
    exec PUT http://localhost:8080/foo/bar -j ./baz.json
    exec PUT http://localhost:8080/foo/bar -e ./a.rb -i 0x000000000001
    http_method: PUT,POST,PATCH,GET,DELETE

Optional arguments:
  -v, -d                print debug protocol messages
  -h, --help            show this help message and exit
  -p, --pp              print http response json with pretty print format
E
end

# main

fname = File.dirname(File.realpath(__FILE__)) + "/eemcli.conf"

if File.exist?(fname)
  File.open(fname) do |f|
    $conf = parse_ini(f.read)
  end
end

server_ip = "localhost"
server_port = "8080"
user = nil
password = nil

def do_if(x)
  yield(x) if x
end

do_if(conf_s("eemcli","server_ip"))   {|x| server_ip = x}
do_if(conf_s("eemcli","server_port")) {|x| server_port = x}
do_if(conf_s("eemcli","user"))        {|x| user = x}
do_if(conf_s("eemcli","password"))    {|x| password = x}

argv = ARGV.dup
argv.extend(OptionParser::Arguable)

if !argv[0]
  usage
  exit
end

case argv[0]
when /-h/
  usage
  exit
when /^eeprom_update/
  f = method(:eeprom_file_check)
  rsc = 'eeprom_update_file'
when /^mms_update/
  f = method(:mms_file_check)
  rsc = 'mms_update_file'
when /^devices?$/
  f = nil
  rsc = 'devices'
when /^exec/,/^do$/
  argv.shift
  $params = argv.getopts("hdv", "pp")
  exec_case_proc(argv, user, password)
  exit
when /^ls$/
  argv.shift
  ds = DestServ.new(server_ip, server_port, user, password)
  include Cmd
  ls_parse(argv, ds)
  exit
else
  usage
  exit
end
argv.shift

$params = argv.getopts("hdvi:", "id:", "pp")
id, a = param_check($params, argv, f)

ds = DestServ.new(server_ip, server_port, user, password)
one_request(ds, rsc, id, a)
