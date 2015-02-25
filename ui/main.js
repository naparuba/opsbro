



Array.prototype.shuffle = function() {
    var i = this.length, j, temp;
    if ( i == 0 ) return this;
    while ( --i ) {
	j = Math.floor( Math.random() * ( i + 1 ) );
	temp = this[i];
	this[i] = this[j];
	this[j] = temp;
    }
    return this;
}


// javascript lak really useful function...
if (typeof String.prototype.startsWith != 'function') {
    String.prototype.startsWith = function (str){
	return this.slice(0, str.length) == str;
    };
}


function parse_uri(uri){
    var parser = document.createElement('a');
    parser.href = uri;
    return parser;
    /*
    parser.protocol; // => "http:"
    parser.host;     // => "example.com:3000"
    parser.hostname; // => "example.com"
    parser.port;     // => "3000"
    parser.pathname; // => "/pathname/"
    parser.hash;     // => "#hash"
    parser.search;   // => "?search=test"
    */
}

// If there is no servers in the config, take the http addr
var server = null;

var def_port = 6768;

if (servers.length == 0){
    var p = parse_uri(window.location);
    servers.push(p.hostname+':'+def_port);
}

// Do not connect always to the same first server, let a chance for other to manage the load
servers.shuffle();

console.log('GET SERVERS'+servers);

// Our list of servers and their states
var pot_servers = {};

$.each(servers, function(_idx, s){
    var elts = s.split(":");
    var hostname = s;
    var port = def_port;
    console.log(elts);
    if (elts.length > 1){
	hostname = elts[0];
	port = parseInt(elts[1]);
    }else{
	s = s+':'+def_port;
    }
    var ws_port = port + 1;
    console.log(s);
    console.log('PORT +'+port);
    pot_servers[s] = {'state':'pending', 'uri':s, port:port, ws_port:ws_port, hostname:hostname, 'elected':false};
});

function update_connexions_view(){
    $('#connexions-ul').html('');
    $.each(pot_servers, function(_idx, e){
	var li = $('<li class="connexion '+e.state+'" id="'+e.hostname+'-'+e.port+'">');
	color = '#ABEBD9'; // blue
	if(e.state == 'ok'){
	    color = '#7bc659'; // green
	}
	if(e.state == 'error'){
	    color = '#dd4e58'; // red
	}
	var p = "<p><span style='color:#FFD357'>"+e.hostname+':'+e.port+"</span>  <span style='color:"+color+"'>"+e.state+"</span>";
	if(e.elected){
	    p += '<span style="color:#c6c5fe"> (elected)</span>';
	}
	p += "</p>";
	li.append(p);
	console.log('ADD');
	console.log(li);
	$('#connexions-ul').append(li);
	console.log($('#connexions-ul'));
    });
}

$(function(){
    update_connexions_view();
});

console.log(pot_servers);

// We will look at all servers and take the first that answer us
function elect_server(){
    $.each(pot_servers, function(s, e){
	var uri = "http://"+s;
	pot_servers[s]['state'] = 'pending';
	pot_servers[s]['elected'] = false; // clean all previous elected thing
	$.ajax({
	    url: uri})
	    .error(function( data ) {
		console.log('PING fail to the server: '+s);
		pot_servers[s]['state'] = 'error';
		update_connexions_view();
	    })	
	    .done(function( data ) {
		console.log('Connexion OK to the server: '+s);
		pot_servers[s]['state'] = 'ok';
		if(server == null){
		    console.log('We just elected a new server: '+s);
		    server = s;
		}
		// If we choose or kept this server as elected, say it
		if(server == s){
		    pot_servers[s]['elected'] = true; // clean all previous elected thing		    
		}
		update_connexions_view();
	    });
    });
}

elect_server();


// Main structure to put nodes and services
var services = [];
var nodes = [];
var is_expanded = false;
var selected = '';



function get_server(){
    
}

function add_spinner(place){
    var opts = {
	lines: 17, // The number of lines to draw
	length: 16, // The length of each line
	width: 4, // The line thickness
	radius: 13, // The radius of the inner circle
	corners: 1, // Corner roundness (0..1)
	rotate: 0, // The rotation offset
	direction: 1, // 1: clockwise, -1: counterclockwise
	color: '#33000', // #rgb or #rrggbb or array of colors
	speed: 1, // Rounds per second
	trail: 66, // Afterglow percentage
	shadow: true, // Whether to render a shadow
	hwaccel: true, // Whether to use hardware acceleration
	className: 'spinner', // The CSS class to assign to the spinner
	zIndex: 2e9, // The z-index (defaults to 2000000000)
	top: '100px', // Top position relative to parent
	left: '50%' // Left position relative to parent
    };
    var target = $(place);
    var spinner = new Spinner(opts).spin();
    target.append(spinner.el);
}


function load_nodes(){
    add_spinner('#nodes');
    var now = new Date().getTime();
    $.getJSON( "http://"+server+"/agent/members?_t="+now, function( data ) {
	var items = [];
	// First put all services into our list
	$.each( data, function( key, val ) {
	    nodes.push(val);
	});
	refresh_nodes();
    });
    
}



function show_services(){
    // Switch services/nodes buttons
    $('#services-btn').addClass('active');
    $('#nodes-btn').removeClass('active');
    $('#connexions-btn').removeClass('active');

    // Show refresh btn only in service page
    $('#refresh-services-btn').show()
    
    // also show services and hide nodes
    $('#services').show();
    $('#nodes').hide();
    // show filters too
    $('#filters').show();

    // and hide the connexion part
    $('#connexions').hide();

}


function show_nodes(){
    // Switch services/nodes buttons
    $('#nodes-btn').addClass('active');
    $('#services-btn').removeClass('active');
    $('#connexions-btn').removeClass('active');

    // Show refresh btn only in service page
    $('#refresh-services-btn').hide()
    
    // also show services and hide nodes
    $('#nodes').show();
    $('#services').hide();
    // Show filters too
    $('#filters').show();

    // and hide the connexion part
    $('#connexions').hide();

}

// Connexions must hide nodes and services and filters
function show_connexions(){
    // Switch services/nodes buttons
    $('#nodes-btn').removeClass('active');
    $('#services-btn').removeClass('active');
    $('#connexions-btn').addClass('active');

    // Show refresh btn only in service page
    $('#refresh-services-btn').hide()
    
    // also show services and hide nodes
    $('#nodes').hide();
    $('#services').hide();
    // Show filters too
    $('#filters').hide();

    // and show the connexions part of course :)
    $('#connexions').show();

}

// Coun the number of node and service, and update the btn badges
function update_counts(){
    $('#badge-nodes').html(nodes.length);
    $('#badge-services').html(services.length);
}

function compare_name(a,b) {
    if (a.name < b.name)
	return -1;
    if (a.name > b.name)
	return 1;
    return 0;
}

function sort_lists(){
    sort_lists_for('nodes');
    sort_lists_for('services');

}

function sort_lists_for(p){
    var mylist = $('#'+p+' > ul');
    var listitems = mylist.children('li').get();
    listitems.sort(function(a, b) {
	return $(a).attr('id').localeCompare($(b).attr('id'));
    })
    $.each(listitems, function(idx, itm) { mylist.append(itm); });
}


function apply_filters(){
    apply_filters_for('nodes');
    apply_filters_for('services');
}

function apply_filters_for(p){
    var reg = $( "#filtername" ).val();
    var state = $( "#filterstate" ).val();

    $('#'+p+' > ul > li').each(function( index ) {
	var li = $(this);
	if(is_expanded){
	    li.find('.compact').hide();
	    li.find('.expanded').show();
	}else{
	    li.find('.compact').show();
	    li.find('.expanded').hide();
	}
    });

    var look_for = 'name';
    // For nodes we can look for others things
    if(p == 'nodes'){
	// Look at filter type
	if(reg.startsWith('t:')){
	    console.log('MATCH TAG');
	    look_for = 'tags';
	}
	
	if(reg.startsWith('s:')){
	    console.log('MATCH SERVICE');
	    look_for = 'services';
	}
    }

    $('#'+p+' > ul > li').each(function( index ) {
	var _id = $(this).attr('id');
	var e_state = $(this).data('state-id');

	
	// We must mauch both name/tag/service and state
	// First name, bail out if no match
	if(look_for == 'name'){
	    if(! (_id.indexOf(reg) > -1)){
		$(this).hide();
		return;
	    }
	}else{// Something will need to find the real node then
	    var node = find_node(_id);
	    if(look_for == 'tags'){
		var tag = reg.replace('t:','')
		// Look for tag and really fot a node
		if(tag!='' && node != null){
		    // Tag not found
		    if(! (node.tags.indexOf(tag) > -1)){
			$(this).hide();
			return;
		    }
		}
	    }
	    if(look_for == 'services'){
		var sname = reg.replace('s:','')
		// Look for service name and really fot a node
		if(sname!='' && node != null){
		    if(!(sname in node.services)){
			$(this).hide();
                        return;
		    }
		}
	    }

	}

	// Here, the name match was not need or false,
	// so look at the state
	if ((state == 'any value') ||
            ((state == 'passing') && (e_state == 0)) ||
            ((state == 'failing') && (e_state == 1 || e_state == 2 || e_state == 3))
           ){
            $(this).show();
        }else{
            $(this).hide();
        }
	return;

	
    });
}




// Binding the filtering part
$(function(){
    // By default show the services
    $('#nodes').hide();
    $('#services').hide();
    
    apply_filters();
    
    $( "#filtername" ).bind('input', function(){
	apply_filters();
    });

    $( "#filterstate" ).on('change', function(){
	apply_filters();
    });

    $('#expand-btn').on('click', function(){
	is_expanded = !is_expanded;
	$(this).toggleClass('active');
	apply_filters();
    });

    show_nodes();

    
    var help_text = ['Nodes:',
		     '<ul>',
		     '<li>string => lookup by the node name</li>',
		     '<li>t:string => lookup by tag name</li>',
		     '<li>s:string => lookup by service name</li>',
		     '</ul>',
		     'Services:',
		     '<ul>',
		     '<li>string => lookup by the service name</li>'		     
		    ].join('\n');

    $('#filter-help').popover({html:true,
			       content:help_text			       
			      } );

});


// Go with all services and print them on the list elements
function refresh_services(){    
    
    var i = 0;
    var items = [];
    for(i=0; i<services.length;i++){
	var val = services[i];
	// Then print all in our filter
	var s = "<li onclick='detail(\"service\",\""+val.name+"\")' class='srv-item list-group-item list-condensed-link' data-state-id='"+val.state_id+"' id='" + val.name + "'>";
	var name = val.name;
	var members = val.members;
	members.sort(function(a, b) {
	    return a.localeCompare(b);
	})

	var failing_members = val['failing-members'];
	var passing_members = val['passing-members'];
	// If len of members is 0, put it in unkown, not normal result here
	var color = 'green';
	var text = ''+passing_members.length+' passing';
	if (members.length == 0){
	    color = 'purple';
	    text = 'no nodes';
	}
	if (failing_members.length > 0){
	    color = 'red';
	    text = ''+failing_members.length+' failing';
	}

	// Compact part
	s += '<div class="compact">';
	s += '<div class="name pull-left">'+name+'</div>';
	s += '<span class="pull-right" style="color:#FF71E2">'+text+'</span>';
	s += '</div>';

	// Expanded version
	s += '<div class="expanded">';
	s += "<h4 class='list-group-item-heading'>&nbsp;";
	s += '<span class="pull-left">'+name+'</span>';
	s += '<span class="pull-right" ><small style="color:#FF71E2">'+text+'</small></span>';
	s += '</h4>'
	s += '<div style="clear: both;"></div>';


	s += '<div class="">';
	s += '<span class="pull-left" style="color:#c6c5fe">Nodes:</span>';
	for(var j=0; j<members.length; j++){
	    mname = members[j];
	    if( failing_members.indexOf(mname) > -1){ // if found
		s += '<span class="pull-left bold" style="color:#dd4e58">'+members[j]+' </span>';
	    }else{
		s += '<span class="pull-left bold">'+members[j]+' </span>';		
	    }
	}
	
	s += '</div>';
	s += '<div style="clear: both;"></div>';

    	
	s += '</div>';

	// Now we can close our li
	s += "</li>";
	items.push( s);
    }
    
    $("#services").html('');
    
    var ul = $( "<ul/>", {
	"class": "service-list",
	html: items.join( "" )
    }).appendTo( "#services" );

    apply_filters();
    sort_lists();
    update_counts();
}




// Generate a LI string with the host information
function generate_host_list_entry(val){
    state_id = 0;
    if(val.state == 'dead'){
	state_id = 2;
    }
    if(val.state == 'suspect'){
	state_id = 1;
    }
    if(val.state == 'leave'){
	state_id = 3;
    }
    var services = val.services;
    // also look at the services states
    $.each( services, function( sname, service ) {
	cstate = service['check'].state_id;
	if (cstate == 2){
	    state_id = 2;
	}
	if(cstate == 1 && state_id < 2){
	    state_id = 1;
	}
    });

    var name = val.name;
    
    var state = val.state;
    // If len of members is 0, put it in unkown, not normal result here
    var color = 'green';
    var text = 'alive';
    if(state == 'alive'){
	if (state_id == 1){
	    color = 'orange';
	}
	if (state_id == 2){
	    color = 'red';
	}
	if (state_id == 3){
	    color = 'gray';
	    }
	
    }
    if (state == 'dead'){
	color = 'red';
    }
    if (state == 'leave'){
	color = 'gray';
    }
    if (state == 'suspect'){
	color = 'orange';
    }

    
    // Then print all in our filter
    var s = "<li onclick='detail(\"node\",\""+val.name+"\")' class='bg-"+color+" list-group-item list-condensed-link ' data-state-id='"+state_id+"' id='" + val.name + "'>";
    // Compact version
    s += '<div class="compact">';
    s += '<div class="name pull-left">'+name+'<br/><small class="pull-left">'+val.addr+'</small>';
    s += '</div>';
    s += '</div>';
    
    
    // Expanded version
    s += '<div class="expanded">';
    s += "<h4 class='list-group-item-heading'>";
    s += name;
    s += '<span class="pull-right"><small style="color:#FF71E2">'+state+'</small></span>';
    s += '</h4>';
    
    s += '<div class=""><span class="pull-left" style="color:#c6c5fe">Addr:</span><span class="pull-left"><small>'+val.addr+'</small></span></div>';
    s += '<div style="clear: both;"></div>';

    s += '<div class="">';
    s += '<span class="pull-left" style="color:#c6c5fe">Tags:</span>';
    $.each( val.tags, function( idx, tname ) {
	s += '<span class="pull-left"><small>'+tname+' </small></span>';
    });
    s += '</div>';

    
    s += '<div style="clear: both;"></div>';

    // get the number of services. Quite not so natural in js ... (ノ ゜Д゜)ノ ︵ ┻━┻
    var nb_s = $.map(services, function(n, i) { return i; }).length;
    if(nb_s > 0){
	s += '<div class="pull-left"  style="color:#c6c5fe">';
	s += '<span>Services:</span>';
	$.each( services, function( sname, service ) {
	    if(service['check'].state == 'OK'){
		s += '<span class="bold">'+sname+'</span>';
	    }
	    if(service['check'].state == 'WARNING'){
		s += '<span class="bold" style="color:#ffac5e;>'+sname+'</span>';
	    }
	    if(service['check'].state == 'CRITICAL'){	    
		s += '<span class="bold" style="color:#dd4e58">'+sname+'</span>';	    
	    }
	    if(service['check'].state == 'UNKNOWN'){
		s += '<span class="bold" style="color:#939393;">'+sname+'</span>';
	    }
	});    
	s += '</div>';
    }
    
    s += '</div>';
    
    s += "</li>";

    return s;

}


// Go with all services and print them on the list elements
function refresh_nodes(){    
    var i = 0;
    var items = [];
    for(i=0; i<nodes.length;i++){
	var val = nodes[i];
	var s = generate_host_list_entry(val);
	items.push( s);
    }
    $("#nodes").html('');
    var ul = $( "<ul/>", {
	"class": "service-list",
	html: items.join( "" )
    }).appendTo( "#nodes" );

    apply_filters();
    sort_lists();
    update_counts();
    
}



function load_services(){
    add_spinner('#services');
    var now = new Date().getTime();
    services = []; // first reset services
    $.getJSON( "http://"+server+"/state/services?_t="+now, function( data ) {
	// First put all services into our list
	$.each( data, function( key, val ) {
	    services.push(val);
	});
	refresh_services();
    });
    
}



function find_node(name){
    var node = null;
    $.each( nodes, function( key, val ) {
	if (val.name == name){
	    node = val;
	}
    });
    return node;
}


function find_service(name){
    var node = null;
    $.each( services, function( key, val ) {
	if (val.name == name){
	    node = val;
	}
    });
    return node;
}


// Detail show be called by a NON modal page
function detail(type, name){
    update_detail(type, name);
    // Show up the modal
    $('.bs-example-modal-lg').modal('show');

}

function update_detail(type, name){
    // We got a click, tag the selected element
    selected = name;
    
    console.log('detail::'+type+'+'+name);
    if(type == 'node'){
	var node = find_node(name);
	if (node == null){
	    $('#part-right').html('<div class="bs-callout bs-callout-warning"><h4>No such node '+name+'</h4></div>');
	}
	var now = new Date().getTime();
	$.getJSON( "http://"+server+"/agent/state/"+name+'?_t='+now, function( data ) {
	    s = '';
	    
	    // modal header part
	    s += '<div class="modal-header">';
            s += '<button type="button" class="close" data-dismiss="modal">';
	    s += '<span aria-hidden="true" style="color:white;">&times;</span><span class="sr-only">Close</span></button>';
            s += '<h4 class="modal-title" id="myModalLabel"><span style="color:#FFD357;">'+node.name+'</span><br/><small style="color:#ABEBD9">'+node.addr+'</small><span class="pull-right" style="color:#FF71E2">'+node.state+'</span></h4>';
            s += '</div>';
	    s += '<div class="modal-body">';

	    s += '<div>'
	    s += '<span class="pull-left" style="color:#c6c5fe">Tags:</span>';
	    $.each( node.tags, function( idx, tname ) {
		s += '<span class="pull-left"><small>'+tname+'&nbsp; </small> </span>';
	    });
	    s += '</div>';

	    s += '<hr/>';
	    
	    // Now print services
	    s += '<div style="color:#c6c5fe">Services:</div>';
	    $.each(data.services, function(k, v){
		var port = v.port;
		if (typeof(port) == 'undefined'){
		    port = '';
		}else{
		    port = ':'+port;
		}
		var color = 'green';
		if(v.check.state == 'WARNING'){
		    color = 'orange';
		}
		if(v.check.state == 'CRITICAL'){
		    color = 'red';
		}
		if(v.check.state == 'UNKNOWN'){
		    color = 'gray';
		}

		
		s += '<div onclick=\'update_detail("service","'+v.name+'")\' class="list-group-item list-condensed-link">';
		s += '<div class="compact"><div class="name" style="color:'+color+';margin-left:10px;">'+v.name+' <span class="pull-right"><small>'+port+'</small></span></div></div>';
		s+= '</div>';
	    });

	    s += '<hr/>';	    
	    
	    // Now print checks
	    s += '<h5>Checks</h5>';
	    $.each(data.checks, function(k, v){
		s += '<div class="list-group-item list-condensed-link">';
		var color = 'green';
		if(v.state == 'WARNING'){
		    color = 'orange';
		}
		if(v.state == 'CRITICAL'){
		    color = 'red';
		}
		if(v.state == 'UNKNOWN'){
		    color = 'gray';
		}
		
		s += '<div class="expanded"><div class="bg-'+color+' list-bar">&nbsp;</div><div class="name bloc-heading">'+v.name+' <span class="pull-right"><small>'+v.state+'</small></span></div></div>';
		//s += '<hr/>';
		if(v.notes != ''){
		    s += '<h5>NOTES</h5>';
		    s += v.notes;
		}
		s += '<h5>OUTPUT</h5>';
		s += '<pre style="background-color:#f0f0f0">'+v.output+'</pre>';
		s+= '</div>';
	    });


	    // close modal body
	    s += '</div>';
	    // and add afooter to close it too	    
	    s += '<div class="modal-footer"><button type="button" class="btn btn-default" data-dismiss="modal">Close</button></div>';
	    
	    $('#part-right').html(s);
	    
	});

    }



    if(type == 'service'){
	var service = find_service(name);
	if (service == null){
	    $('#part-right').html('<div class="bs-callout bs-callout-warning"><h4>No such service '+name+'</h4></div>');
	}
	s = '';

	// modal header part
	s += '<div class="modal-header">';
        s += '<button type="button" class="close" data-dismiss="modal">';
	s += '<span aria-hidden="true" style="color:white;">&times;</span><span class="sr-only">Close</span></button>';
        s += '<h4 class="modal-title" id="myModalLabel" style="color: #FFD357;">'+service.name+'</h4>';
        s += '</div>';
	s += '<div class="modal-body">';


	// Now print hosts
	s += '<h5 style="color: #c6c5fe;">Hosts:</h5>';

	var sub_hosts = {};
	// We will concatenate the right part of the service detail with all hosts by sort them by the node name
	// and link all with the s from the detail header
	function update_service_right_part(){
	    //first sort the sub_hosts by their names
	    var node_names = [];
	    $.each(sub_hosts, function(key, value) {
		node_names.push(key);
	    });
	    node_names.sort();
	    var f = s;
	    $.each(node_names, function(idx, nname) {
		var sh = sub_hosts[nname];
		f += sh;
            });

	    // close modal body
	    f += '</div>';
	    // and add afooter to close it too	    
	    f += '<div class="modal-footer"><button type="button" class="btn btn-default" data-dismiss="modal">Close</button></div>';

	    $('#part-right').html(f);
	}
	
	$.each( service.members, function( idx, hname ) {
	    var now = new Date().getTime();
	    $.getJSON( "http://"+server+"/agent/state/"+hname+'?_t='+now, function( data ) {
		var sh = '';
		var node = find_node(hname);
		if (node == null){
		    return;
		}
		

		var state = node.state;
		var color = 'gray';
		if(state == 'alive'){
		    color = '#bbf085';//green
		}
		
		if (state == 'dead'){
		    color = '#dd4e58'; // red
		}
		if (state == 'leave'){
		    color = 'gray';
		}
		if (state == 'suspect'){
		    color = 'orange';
		}


		sh += '<div class="compact show-pointer" style="height: 25px;" onclick="update_detail(\'node\',\''+node.name+'\')"><div class="name">'+node.name+'<small> ('+node.addr+')</small> <span class="pull-right"><span style="color:'+color+'">'+node.state+'</span></span></div></div>';

		$.each(data.checks, function(k, v){
		    sh += '<ul style="margin-bottom: 0px;">';
		    var color = 'green';
		    if(v.state == 'WARNING'){
			color = 'orange';
		    }
		    if(v.state == 'CRITICAL'){
			color = '#dd4e58'; // red
		    }
		    if(v.state == 'UNKNOWN'){
			color = 'gray';
		    }
		    
		    sh += '<li style="list-style-type: none"><div class="compact" style="height: 25px;"  ><div class="name">'+v.name+' <span class="pull-right"><small style="color:'+color+'">'+v.state+'</small></span></div></div></li>';
		    sh += '</ul>';
		    
		});

		
		// Ok add it to the s part
		sub_hosts[node.name] = sh;
		
		update_service_right_part()

		
	    }); // end of the loop other the hname node
	});// End of all service.members

	update_service_right_part();

    }

    // Show up the modal
    $('.bs-example-modal-lg').modal('show');
}


// Ok let's roll and really connect to our main server at soon
// as it is connected :)
$(function(){
    function do_load(){
	if(server != null){
	    console.log('OK Election is done, we can load');
	    load_nodes();
	    load_services();
	}else{
	    console.log('Cannot load, waiting server elecgtion');
	    setTimeout(do_load, 100);
	}
    }

    do_load();
});



var webso_con = null;

function do_webso_connect(){

    // No server to connect to, do nothing a wait a new can be elected
    if (server == null){
	$('#icon-connexion').addClass('red');
	$('#icon-connexion').attr('data-original-title', 'Websocket: ✘').tooltip('fixTitle');
	elect_server();
	return;
    }

    if (webso_con == null){
	var e = pot_servers[server];
	console.log('Connexion try to websocket');
	var ws_uri = 'ws://'+e.hostname+':'+e.ws_port+'/ws';
	console.log('Connexion to websocket: '+ws_uri);
	webso_con = new WebSocket(ws_uri);
	$('#icon-connexion').tooltip({title:'Connexion to websocket in progress'});
	webso_con.onopen = function(){
	    console.log('Connection open!');
	    // We remove the red from the icon so it's back to black
	    $('#icon-connexion').removeClass('red');
	    $('#icon-connexion').attr('data-original-title', 'Websocket: ✔').tooltip('fixTitle');
	}

	webso_con.onerror = function(){
	    webso_con = null;
	    // Put the icon for connexion in red
	    $('#icon-connexion').addClass('red');
	    $('#icon-connexion').attr('data-original-title', 'Websocket: ✘').tooltip('fixTitle');
	    console.log('Wesocket connection error to '+ws_uri);
	    server = null;
	    // We got a problem, reelect a new server
	    elect_server();
	}

	webso_con.onclose = function (e) {
	    webso_con = null;
	    // Put the icon for connexion in red
	    $('#icon-connexion').addClass('red');
	    $('#icon-connexion').attr('data-original-title', 'Websocket: ✘').tooltip('fixTitle');
	    console.log('Wesocket connection error to '+ws_uri);
	    server = null;
	    // A problem? let's look at a new server to laod from
	    elect_server();
	};
    
	webso_con.onmessage = function (e) {
	    console.log("Socket message:", e.data);
	    // Load the host update as a json dict
	    var oraw = JSON.parse(e.data);
	    if(oraw.channel != 'gossip'){
		console.log('Unmanaged websocket message '+ oraw);
		return;
	    }
	    
	    o = oraw.payload;
	    
	    var name = o.name;
	    // Delete the previously add host
	    nodes = $.grep(nodes, function(h) {
		return h.name != name;
	    });
	    // Save this host in the list :)
	    nodes.push(o);
	    // Now generate the doc string from our new host
	    var s = generate_host_list_entry(o);
	    // Delete the previous li for this node
	    $('#'+name).remove();
	    // ok add new the one
	    $(s).appendTo($('#nodes > ul'));
	    // resort and hide if need
	    apply_filters();
	    sort_lists();
	    update_counts();
	    // If it was teh selected, update the detail panel
	    console.log('SELECTED '+selected+' AND '+name);
	    if(name == selected){
		detail('node', name);
	    }
	};
    }
}

setInterval(do_webso_connect, 1000);

$(function(){
    do_webso_connect();
});


