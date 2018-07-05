module RestC

  def self.get_body(url, ds, data=nil)
    uri = URI.parse(url)
    http = Net::HTTP.new(uri.host, uri.port)
    if conf_is?("eemcli", "debughttplib", "true")
      http.set_debug_output($stderr)
    end
    req = Net::HTTP::Get.new(uri.request_uri)
    req.basic_auth(ds.user, ds.password) if ds.user
    req['Content-Type'] = type if data
    req['Accept'] = "application/json"

    response = http.request(req, data)
    response.body
  end

  def self.get_gids(ds)
    url = "http://#{ds.ip}:#{ds.port}/eem/groups"
    get_body(url, ds)
  end

  def self.get_ids(ds)
    url = "http://#{ds.ip}:#{ds.port}/eem/devices"
    get_body(url, ds)
  end

  #
  # @return JSON string or raise error.
  #
  def self.get_ids_detail(ds, gid=nil)
    # 3.3.7 List Devices
    #       List Devices Details
    # 3.3.8 Show Device
    # See sample ticket:68#comment:21
    #            ticket:74#comment:4
    if gid
      url = "http://#{ds.ip}:#{ds.port}/eem/devices/detail?group_id=#{gid}"
    else
      url = "http://#{ds.ip}:#{ds.port}/eem/devices/detail"
    end
    get_body(url, ds)
  end

  def self.get_uid_jsonstr(id, ds)
    url = "http://#{ds.ip}:#{ds.port}/eem/devices/#{id}/uid_led_status"
    get_body(url, ds)
  end

  def self.get_rotary_jsonstr(id, ds)
    url = "http://#{ds.ip}:#{ds.port}/eem/devices/#{id}/rotary_switch_status"
    get_body(url, ds)
  end

end

#require_relative 'cli-reststub'

module Cmd

  @@now = Time.now

  def puts_date
    puts "Date: " + Time.now.strftime("%F %T")
  end

  #
  # @param long_val the value string of datetime (Java long value)
  # @param short_fmt the short format(date only) flag.
  #
  def time_str(long_val, short_fmt=false)
    return "-" if long_val.nil?
    if short_fmt
      Time.at(long_val.to_i/1000).strftime("%F")
    else
      Time.at(long_val.to_i/1000).strftime("%F %T.") + 
              format("%03d", long_val.to_i % 1000)
    end
  end

  #
  # Time(today) or date
  # @param long_val the value string of datetime (Java long value)
  #
  def time_date(long_val)
    return "-" if long_val.nil?
    time = Time.at(long_val.to_i/1000)
    if @@now.strftime("%F") == time.strftime("%F")
      # today
      time.strftime("%T.") + format("%03d", long_val.to_i % 1000)
    else
      time.strftime("%F ") + (time.hour >= 12 ? "PM" : "AM")
    end
  end
  
  def dead_alive_str(i)
    return "-" if i["notification_status0"].nil?
    down = ["down", "down"]
    if i["notification_status0"] == down &&
       i["notification_status1"] == down
      "dead"
    else
      "alive"
    end
  end
  
  #
  # ls command.
  #
  # Intermediate input
  # - device id list (detailed info at once)
  #
  # Display item
  # - device id
  # - EESV/EEIO
  # - update_time
  # - alive/dead
  #
  def ls_cmd(argv, ds)
    # json handling and human readable format layer
    jstr = RestC.get_ids_detail(ds)
    j = jstr.empty? ? {"devices" => []} : JSON.parse(jstr)
    puts_date
    puts <<'HEADER'
 EE card ID    sv/io dead? Update time
-------------- ----- ----- -----------------------
HEADER
    j["devices"].each do |i|
      printf "%s %-5s %-5s %s\n", i["id"], i["status"],
             dead_alive_str(i), 
             time_str(i["update_time"])
    end
    printf "Total count: %d%s\n", j["devices"].size,
      (j["devices"].empty? ? " (No entry)" : "")
    printf   "Timestamp  : %s\n", time_str(j["timestamp"])
    puts_date
  end
  
  
  #
  # Print trailer/footer (Total count).
  #
  def gid_trailer_print(ngids, count)
    printf "GIDs count : %4d\n", ngids
    printf "Total count: %4d%s\n", count,
      (count == 0 ? " (No entry)" : "")
    puts_date
  end

  #
  # Targeted gids getter. return numeric array.
  #
  def targ_gids_get(ds, gids)
      return gids if gids
      jstr = RestC.get_gids(ds)
      j = jstr.empty? ? {"groups" => []} : JSON.parse(jstr)
      gids = j["groups"].map{|i| i["id"].to_i}
  end
  
  #
  # ls -g -j command.
  # json format
  #
  def ls_g_j_cmd(argv, ds, gids)
    puts_date
    gids = targ_gids_get(ds, gids)
  
    puts <<'HEADER'
 GID
----
HEADER
    count = 0
    gids.each do |i|
      printf "%4d\n", i
      jstr = RestC.get_ids_detail(ds, i)
      jj = jstr.empty? ? {"devices" => []} : JSON.parse(jstr)
      #puts JSON.pretty_generate(jj)
      jj["devices"].each do |x|
        puts JSON.generate(x)
        count += 1
      end
    end
    gid_trailer_print(gids.size, count)
  end
  
  #
  # ls -g -l
  #
  # Intermediate input
  # - group id list
  # - each device detail
  # - uid_led_status
  # - rotary_switch_status
  #
  def ls_g_l_cmd(argv, ds, gids)

    gids = targ_gids_get(ds, gids)
 
    puts_date
    puts <<'HEADER'
 GID EE card ID     sv/io dead? Updated    UID Rot
---- -------------- ----- ----- ---------- --- ---
HEADER
    count = 0
    gids.each do |i|
      printf "%4d\n", i
      jstr = RestC.get_ids_detail(ds, i)
      jj = jstr.empty? ? {"devices" => []} : JSON.parse(jstr)
      jj["devices"].sort do |x, y|
        [y["status"], dead_alive_str(x), x["id"]] <=>
        [x["status"], dead_alive_str(y), y["id"]]
      end.each do |x|
        jstr = RestC.get_uid_jsonstr(x["id"], ds)
        j3 = jstr.empty? ? {} : JSON.parse(jstr)
        jstr = RestC.get_rotary_jsonstr(x["id"], ds)
        j4 = jstr.empty? ? {} : JSON.parse(jstr)
        printf(if j3["uid_led_status"] == "on"
                 "%4s \e[1m%s\e[0m %-5s %-5s %s \e[32;1m%-3s\e[0m %3s\n"
               else
                 "%4s %s %-5s %-5s %s %-3s %3s\n"
               end,
               x["group_id"], x["id"], x["status"],
               dead_alive_str(x),
               time_str(x["update_time"], true),
               j3["uid_led_status"], j4["rotary_switch_status"])
        count += 1
      end
    end
    gid_trailer_print(gids.size, count)
  end

  #
  # roundup to even number.
  #
  # 3 -> 4
  # 4 -> 4
  #
  def roundup_even(x)
    (x / 2.0).ceil * 2
  end

  #
  # downstream port expand format.
  #
  # @param dp the array of downstream ports. (JSON object style)
  #
  def dp_format(dp)
    return if dp.nil?
    num = dp.size
    rows = roundup_even((num / 3.0).ceil)

    printf("     +\n")
    h = dp.group_by{|x| x["downstream_port_id"].to_i % rows}
    h.keys.each do |k|
      printf("     ")
      puts (h[k].map{|x| format("%2s) %s", x["downstream_port_id"],
        x["eeio_mac_address"]) }.join(' '))
    end
    printf("     +\n")
  end

  def intvec_str(s)
    return "-" if s.nil?
    format("0x%02x", s.hex)
  end

  #
  # ls -g -v (verbose)
  #
  # Print with downstream port expanding.
  #
  def ls_g_v_cmd(argv, ds, gids)
 
    gids = targ_gids_get(ds, gids)
 
    puts_date
    puts <<'HEADER'
 GID EE card ID     sv/io type dead? Intvec Updated
---- -------------- ----- ---- ----- ------ -------------
HEADER
    count = 0
    gids.each do |i|
      printf "%4d\n", i
      jstr = RestC.get_ids_detail(ds, i)
      jj = jstr.empty? ? {"devices" => []} : JSON.parse(jstr)
      jj["devices"].sort do |x, y|
        [y["status"], dead_alive_str(x), x["id"]] <=>
        [x["status"], dead_alive_str(y), y["id"]]
      end.each do |x|
        printf("%4s %s %-5s %-4s %-5s %6s %s\n",
               x["group_id"], x["id"], x["status"],
	       x["type"],
               dead_alive_str(x),
	       intvec_str(x["interrupt_vector"]),
               time_date(x["update_time"]))
        dp_format(x["downstream_ports"])
        count += 1
      end
    end
    gid_trailer_print(gids.size, count)
  end
 
  def aux_fields_get(argv)
    return [] if argv.size == 0
    case argv[0]
    when '-a'
      a = argv[1].split(',')
      a
    end
  end

  #
  # Parse gid range and return numeric array. rejects 0.
  #
  # 1
  # 5-7
  # 5-7,10
  #
  def gid_range_parse(s)
    a = s.split(',').map{|x| x.split('-')}.map{|x| x.map{|y| y.to_i}}
    a.each do |x|
      return -1 if x[0] == 0
    end
    a.map{|x| (x[0]..x[x.size-1]).to_a }.flatten
  end

  #
  # ls -g command.
  #
  # Intermediate input
  # - group id list
  # - each device detail
  #
  # Display item
  # - group id
  # - device id
  # - EESV/EEIO
  # - update_time
  # - alive/dead
  #
  def ls_g_cmd(argv, ds)
    # json handling and human readable format layer
    aux_fields = []
    gids = nil
    while argv[0]
      case argv[0]
      when '-a'
        aux_fields = aux_fields_get(argv)
        argv.shift(2)
      when '-j'
        ls_g_j_cmd(argv, ds, gids)
        return
      when '-l'
        ls_g_l_cmd(argv, ds, gids)
        return
      when '-v'
        ls_g_v_cmd(argv, ds, gids)
        return
      when nil
      else
        gids = gid_range_parse(argv[0])
        if gids == -1
          puts "Usage: ls -g [[<gid,...>] [-a field1,field2,...|-j|-l|-v]]"
          puts "e.g.   ls -g -a uid_switch_status,path_status0"
          raise ArgumentError.new "illegal option '#{argv[0]}'"
        end
        argv.shift
      end
    end

    width = 8
    gids = targ_gids_get(ds, gids)
    short_fmt = !aux_fields.empty?
    puts_date
    printf "%s",
      if short_fmt
        " GID EE card ID     sv/io dead? Updated   "
      else
        " GID EE card ID     sv/io dead? Update time            "
      end
    puts aux_fields.map{|x| " " + format("%-*.*s", width, width, x)}.join
    printf "%s",
      if short_fmt
        "---- -------------- ----- ----- ----------"
      else
        "---- -------------- ----- ----- -----------------------"
      end
    puts aux_fields.map{|x| " " + "-"*8}.join
    count = 0
    gids.each do |i|
      printf "%4d\n", i
      jstr = RestC.get_ids_detail(ds, i)
      jj = jstr.empty? ? {"devices" => []} : JSON.parse(jstr)
      a = jj["devices"]
      a.sort do |x, y|
        [y["status"], dead_alive_str(x), x["id"]] <=>
        [x["status"], dead_alive_str(y), y["id"]]
      end.each do |x|
        printf "%4s %s %-5s %-5s %s",
               x["group_id"], x["id"], x["status"],
               dead_alive_str(x),
               time_str(x["update_time"], short_fmt)
        aux_fields.each do |k|
          printf " %-*.*s", width, width, x[k]
        end
        printf "\n"
        count += 1
      end
    end
    gid_trailer_print(gids.size, count)
  end
 
  #
  # ls command parse
  #
  def ls_parse(argv, ds)
    if argv.size == 0
      ls_cmd(argv, ds)
      return
    end
    case argv[0]
    when '-g'
      argv.shift
      ls_g_cmd(argv, ds)
    when '-h'
      puts "Usage: ls [-g [<gid,...>] [-a field1,field2,...|-j|-l|-v]]"
    else
      puts "illegal option '#{argv[0]}'"
    end
  end

end
