#!/usr/bin/env ruby

require 'test/unit'
require 'json'
require 'stringio'
require_relative 'cli-rest.rb'
require_relative 'cli-reststub.rb'
include Cmd

module Cmd
  @@now = Time.new(2015,4,14)
end

class TestCmd < Test::Unit::TestCase
  def setup
    @sio = StringIO.new
    $stdout = @sio
  rescue
    $stderr.puts "rescue"
  ensure
    #$stderr.puts "ensure"
  end

  def teardown
    $stdout = STDOUT
    @sio.rewind
    while line = @sio.gets
      #puts line
    end
    @sio.close
  end
  
  def test0_ls()
    ls_parse([], nil)
    #$stderr.puts @sio.string
    assert(/Total count: 4/ =~ @sio.string, "ls")
    assert(/Timestamp  : 2015-04-26 01:29:09.749/ =~ @sio.string, "Timestamp")
    assert_match('Timestamp  : 2015-04-26 01:29:09.749', @sio.string)
  end

  def test1_ls_g()
    ls_parse(["-g"], nil)
    #$stderr.puts @sio.string
    assert(/Total count:    8/ =~ @sio.string, "ls -g")
  end

  def test2_ls_g_a()
    ls_parse(["-g", "-a",
      "uid_switch_status,link_status0,eesv_connection_status"], nil)
    assert(/Total count:    8/ =~ @sio.string, "ls -g -a")
  end

  def test3_ls_g_l()
    ls_parse(["-g", "-l"], nil)
    assert(/Total count:    8/ =~ @sio.string, "ls -g -l")
  end

  def test4_ls_g_v()
    ls_parse(["-g", "-v"], nil)
    #$stderr.puts @sio.string
    assert(/Total count:    8/ =~ @sio.string, "ls -g -v")
  end

end
