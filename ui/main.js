// Add a way to shuffle an array
Array.prototype.shuffle = function() {
    var i = this.length, j, temp;
    if ( i == 0 ) {
        return this;
    }
    while ( --i ) {
        j         = Math.floor( Math.random() * ( i + 1 ) );
        temp      = this[ i ];
        this[ i ] = this[ j ];
        this[ j ] = temp;
    }
    return this;
};

// javascript lack really useful function...
if ( typeof String.prototype.startsWith != 'function' ) {
    String.prototype.startsWith = function( str ) {
        return this.slice( 0, str.length ) == str;
    };
}

function parse_uri( uri ) {
    var parser  = document.createElement( 'a' );
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

if ( servers.length == 0 ) {
    var p = parse_uri( window.location );
    servers.push( p.hostname + ':' + def_port );
}

// Do not connect always to the same first server, let a chance for other to manage the load
servers.shuffle();

console.debug( 'GET SERVERS' + servers );

// Our list of servers and their states
var pot_servers = {};

$.each( servers, function( _idx, s ) {
    var elts     = s.split( ":" );
    var hostname = s;
    var port     = def_port;
    console.log( elts );
    if ( elts.length > 1 ) {
        hostname = elts[ 0 ];
        port     = parseInt( elts[ 1 ] );
    } else {
        s = s + ':' + def_port;
    }
    var ws_port = port + 1;
    console.debug( s );
    console.debug( 'PORT +' + port );
    pot_servers[ s ] = { 'state': 'pending', 'uri': s, port: port, ws_port: ws_port, hostname: hostname, 'elected': false };
} );

function update_connexions_view() {
    var ul = $( '#connexions-ul' );
    ul.html( '' );
    $.each( pot_servers, function( _idx, e ) {
        var li    = $( '<li class="connexion ' + e.state + '" id="' + e.hostname + '-' + e.port + '">' );
        var color = '#ABEBD9'; // blue
        if ( e.state == 'ok' ) {
            color = '#7bc659'; // green
        }
        if ( e.state == 'error' ) {
            color = '#dd4e58'; // red
        }
        var p = "<p><span style='color:#FFD357'>" + e.hostname + ':' + e.port + "</span>  <span style='color:" + color + "'>" + e.state + "</span>";
        if ( e.elected ) {
            p += '<span style="color:#C6C5FE"> (elected)</span>';
        }
        p += "</p>";
        li.append( p );
        ul.append( li );
    } );
}

$( function() {
    update_connexions_view();
} );

console.debug( pot_servers );

// We will look at all servers and take the first that answer us
function elect_server() {
    $.each( pot_servers, function( s ) {
        var uri                       = "http://" + s;
        pot_servers[ s ][ 'state' ]   = 'pending';
        pot_servers[ s ][ 'elected' ] = false; // clean all previous elected thing
        $.ajax( {
            url: uri
        } )
            .error( function() {
                console.log( 'PING fail to the server: ' + s );
                pot_servers[ s ][ 'state' ] = 'error';
                update_connexions_view();
            } )
            .done( function() {
                console.log( 'Connexion OK to the server: ' + s );
                pot_servers[ s ][ 'state' ] = 'ok';
                if ( server == null ) {
                    console.log( 'We just elected a new server: ' + s );
                    server = s;
                }
                // If we choose or kept this server as elected, say it
                if ( server == s ) {
                    pot_servers[ s ][ 'elected' ] = true; // clean all previous elected thing
                }
                update_connexions_view();
            } );
    } );
}

elect_server();

// Main structure to put nodes
var nodes       = [];
var is_expanded = false;
var selected    = '';

function add_spinner( place ) {
    var opts    = {
        lines:     17, // The number of lines to draw
        length:    16, // The length of each line
        width:     4, // The line thickness
        radius:    13, // The radius of the inner circle
        corners:   1, // Corner roundness (0..1)
        rotate:    0, // The rotation offset
        direction: 1, // 1: clockwise, -1: counterclockwise
        color:     '#33000', // #rgb or #rrggbb or array of colors
        speed:     1, // Rounds per second
        trail:     66, // Afterglow percentage
        shadow:    true, // Whether to render a shadow
        hwaccel:   true, // Whether to use hardware acceleration
        className: 'spinner', // The CSS class to assign to the spinner
        zIndex:    2e9, // The z-index (defaults to 2000000000)
        top:       '100px', // Top position relative to parent
        left:      '50%' // Left position relative to parent
    };
    var target  = $( place );
    var spinner = new Spinner( opts ).spin();
    target.append( spinner.el );
}

function Node( gossip_entry ) {
    var properties = [ 'uuid', 'addr', 'checks', 'incarnation', 'name', 'port', 'state', 'tags' ];  // to copy from gossip
    for ( var i = 0; i < properties.length; i++ ) {
        var k     = properties[ i ];
        this[ k ] = gossip_entry[ k ];
    }
}

Node.prototype.print = function() {
    console.log( 'Node: [name=' + this.addr + ']' );
    console.log( this );
};

function load_nodes() {
    add_spinner( '#nodes' );
    var now = new Date().getTime();
    $.getJSON( "http://" + server + "/agent/members?_t=" + now, function( data ) {
        // First put all nodes into our list
        $.each( data, function( key, val ) {
            //console.log(val);
            var n = new Node( val );
            n.print();
            nodes.push( n ); //val );
        } );
        refresh_nodes();
    } );
}

function show_nodes() {
    // Switch nodes buttons
    $( '#nodes-btn' ).addClass( 'active' );
    $( '#connexions-btn' ).removeClass( 'active' );
    
    // also show services and hide nodes
    $( '#nodes' ).show();
    
    // Show filters too
    $( '#filters' ).show();
    
    // and hide the connexion part
    $( '#connexions' ).hide();
}

// Connexions must hide nodes and services and filters
function show_connexions() {
    // Switch services/nodes buttons
    $( '#nodes-btn' ).removeClass( 'active' );
    
    $( '#connexions-btn' ).addClass( 'active' );
    
    // also show services and hide nodes
    $( '#nodes' ).hide();
    
    // Show filters too
    $( '#filters' ).hide();
    
    // and show the connexions part of course :)
    $( '#connexions' ).show();
}

// Coun the number of node and service, and update the btn badges
function update_counts() {
    $( '#badge-nodes' ).html( nodes.length );
}

function sort_lists() {
    sort_lists_for( 'nodes' );
}

function sort_lists_for( p ) {
    var mylist    = $( '#' + p + ' > ul' );
    var listitems = mylist.children( 'li' ).get();
    listitems.sort( function( a, b ) {
        return $( a ).attr( 'id' ).localeCompare( $( b ).attr( 'id' ) );
    } );
    $.each( listitems, function( idx, itm ) {
        mylist.append( itm );
    } );
}

function apply_filters() {
    apply_filters_for( 'nodes' );
}

function apply_filters_for( p ) {
    var reg   = $( "#filtername" ).val();
    var state = $( "#filterstate" ).val();
    
    var lis = $( '#' + p + ' > ul > li' );
    
    lis.each( function() {
        var li = $( this );
        if ( is_expanded ) {
            li.find( '.compact' ).hide();
            li.find( '.expanded' ).show();
        } else {
            li.find( '.compact' ).show();
            li.find( '.expanded' ).hide();
        }
    } );
    
    var look_for = 'name';
    // For nodes we can look for others things
    if ( p == 'nodes' ) {
        // Look at filter type
        if ( reg.startsWith( 't:' ) ) {
            console.debug( 'MATCH TAG' );
            look_for = 'tags';
        }
        
    }
    
    lis.each( function() {
        var _id     = $( this ).attr( 'id' );
        var e_state = $( this ).data( 'state-id' );
        
        // We must mauch both name/tag/service and state
        // First name, bail out if no match
        if ( look_for == 'name' ) {
            if ( !(_id.indexOf( reg ) > -1) ) {
                $( this ).hide();
                return;
            }
        } else {// Something will need to find the real node then
            var node = find_node( _id );
            if ( look_for == 'tags' ) {
                var tag = reg.replace( 't:', '' );
                // Look for tag and really fot a node
                if ( tag != '' && node != null ) {
                    // Tag not found
                    if ( !(node.tags.indexOf( tag ) > -1) ) {
                        $( this ).hide();
                        return;
                    }
                }
            }
            
        }
        
        // Here, the name match was not need or false,
        // so look at the state
        if ( (state == 'any value') ||
             ((state == 'passing') && (e_state == 0)) ||
             ((state == 'failing') && (e_state == 1 || e_state == 2 || e_state == 3))
        ) {
            $( this ).show();
        } else {
            $( this ).hide();
        }
    } );
}

// Binding the filtering part
$( function() {
    // By default show the nodes
    $( '#nodes' ).hide();
    
    apply_filters();
    
    $( "#filtername" ).bind( 'input', function() {
        apply_filters();
    } );
    
    $( "#filterstate" ).on( 'change', function() {
        apply_filters();
    } );
    
    $( '#expand-btn' ).on( 'click', function() {
        is_expanded = !is_expanded;
        $( this ).toggleClass( 'active' );
        apply_filters();
    } );
    
    show_nodes();
    
    var help_text = [ 'Nodes:',
                      '<ul>',
                      '<li>string => lookup by the node name</li>',
                      '<li>t:string => lookup by tag name</li>',
                      '<li>s:string => lookup by service name</li>',
                      '</ul>',
                      'Services:',
                      '<ul>',
                      '<li>string => lookup by the service name</li>'
    ].join( '\n' );
    
    $( '#filter-help' ).popover( {
        html:    true,
        content: help_text
    } );
    
} );

// Generate a LI string with the host information
function generate_host_list_entry( val ) {
    var state_id = 0;
    if ( val.state == 'dead' ) {
        state_id = 2;
    }
    if ( val.state == 'suspect' ) {
        state_id = 1;
    }
    if ( val.state == 'leave' ) {
        state_id = 3;
    }
    
    var nuuid = val.uuid;
    
    var state = val.state;
    // If len of members is 0, put it in unknown, not normal result here
    var color = 'green';
    if ( state == 'alive' ) {
        if ( state_id == 1 ) {
            color = 'orange';
        }
        if ( state_id == 2 ) {
            color = 'red';
        }
        if ( state_id == 3 ) {
            color = 'gray';
        }
        
    }
    if ( state == 'dead' ) {
        color = 'red';
    }
    if ( state == 'leave' ) {
        color = 'gray';
    }
    if ( state == 'suspect' ) {
        color = 'orange';
    }
    
    // Then print all in our filter
    var s = "<li onclick='detail(\"node\",\"" + nuuid + "\")' class='bg-" + color + " list-group-item list-condensed-link ' data-state-id='" + state_id + "' id='" + nuuid + "'>";
    // Compact version
    s += '<div class="compact">';
    s += '<div class="name pull-left">' + val.name + '<br/><small class="pull-left">' + val.addr + '</small>';
    s += '</div>';
    s += '</div>';
    
    // Expanded version
    s += '<div class="expanded">';
    s += "<h4 class='list-group-item-heading'>";
    s += val.name;
    s += '<span class="pull-right"><small style="color:#FF71E2">' + state + '</small></span>';
    s += '</h4>';
    
    s += '<div class=""><span class="pull-left" style="color:#C6C5FE">Addr:</span><span class="pull-left"><small>' + val.addr + '</small></span></div>';
    s += '<div style="clear: both;"></div>';
    
    s += '<div class="">';
    s += '<span class="pull-left" style="color:#C6C5FE">Tags:</span>';
    $.each( val.tags, function( idx, tname ) {
        s += '<span class="pull-left"><small>' + tname + ' </small></span>';
    } );
    s += '</div>';
    
    s += '<div style="clear: both;"></div>';
    
    s += '</div>';
    
    s += "</li>";
    
    return s;
    
}

// Go with all nodes and print them on the list elements
function refresh_nodes() {
    var items = [];
    for ( var i = 0; i < nodes.length; i++ ) {
        var val = nodes[ i ];
        var s   = generate_host_list_entry( val );
        items.push( s );
    }
    $( "#nodes" ).html( '' );
    var ul = $( "<ul/>", {
        "class": "service-list",
        html:    items.join( "" )
    } ).appendTo( "#nodes" );
    
    apply_filters();
    sort_lists();
    update_counts();
    
}

function find_node( nuuid ) {
    var node = null;
    $.each( nodes, function( key, val ) {
        if ( val.uuid == nuuid ) {
            node = val;
        }
    } );
    return node;
}

// Detail show be called by a NON modal page
function detail( type, nuuid ) {
    console.debug( 'GET DETAIL FOR' + type + ' => ' + nuuid );
    update_detail( type, nuuid );
    // Show up the modal
    $( '.bs-example-modal-lg' ).modal( 'show' );
    
}

function update_detail( type, nuuid ) {
    // We got a click, tag the selected element
    selected = nuuid;
    
    console.debug( 'detail::' + type + '+' + nuuid );
    if ( type == 'node' ) {
        var node = find_node( nuuid );
        if ( node == null ) {
            $( '#part-right' ).html( '<div class="bs-callout bs-callout-warning"><h4>No such node ' + nuuid + '</h4></div>' );
        }
        var now = new Date().getTime();
        $.getJSON( "http://" + server + "/agent/state/" + nuuid + '?_t=' + now, function( data ) {
            var s = '';
            
            // modal header part
            s += '<div class="modal-header">';
            s += '<button type="button" class="close" data-dismiss="modal">';
            s += '<span aria-hidden="true" style="color:white;">&times;</span><span class="sr-only">Close</span></button>';
            s += '<h4 class="modal-title" id="myModalLabel"><span style="color:#FFD357;">' + node.name + '</span><br/><small style="color:#ABEBD9">' + node.addr + '</small><span class="pull-right" style="color:#FF71E2">' + node.state + '</span></h4>';
            s += '</div>';
            s += '<div class="modal-body">';
            
            s += '<div>';
            s += '<span class="pull-left" style="color:#C6C5FE">Tags:</span>';
            $.each( node.tags, function( idx, tname ) {
                s += '<span class="pull-left"><small>' + tname + '&nbsp; </small> </span>';
            } );
            s += '</div>';
            
            s += '<hr/>';
            
            s += '<hr/>';
            
            // Now print checks
            s += '<h5>Checks</h5>';
            $.each( data.checks, function( k, v ) {
                s += '<div class="list-group-item list-condensed-link">';
                var color = 'green';
                if ( v.state == 'WARNING' ) {
                    color = 'orange';
                }
                if ( v.state == 'CRITICAL' ) {
                    color = 'red';
                }
                if ( v.state == 'UNKNOWN' ) {
                    color = 'gray';
                }
                
                s += '<div class="expanded"><div class="bg-' + color + ' list-bar">&nbsp;</div><div class="name bloc-heading">' + v.name + ' <span class="pull-right"><small>' + v.state + '</small></span></div></div>';
                
                if ( v.notes != '' ) {
                    s += '<h5>NOTES</h5>';
                    s += v.notes;
                }
                s += '<h5>OUTPUT</h5>';
                s += '<pre style="background-color:#F0F0F0">' + v.output + '</pre>';
                s += '</div>';
            } );
            
            // close modal body
            s += '</div>';
            // and add afooter to close it too
            s += '<div class="modal-footer"><button type="button" class="btn btn-default" data-dismiss="modal">Close</button></div>';
            
            $( '#part-right' ).html( s );
            
        } );
        
    }
    
    // Show up the modal
    $( '.bs-example-modal-lg' ).modal( 'show' );
}

// Ok let's roll and really connect to our main server at soon
// as it is connected :)
$( function() {
    function do_load() {
        if ( server != null ) {
            console.log( 'OK Election is done, we can load' );
            load_nodes();
        } else {
            console.log( 'Cannot load, waiting server elecgtion' );
            setTimeout( do_load, 100 );
        }
    }
    
    do_load();
} );

var webso_con = null;

function do_webso_connect() {
    
    // No server to connect to, do nothing a wait a new can be elected
    var icon_connexion = $( '#icon-connexion' );
    if ( server == null ) {
        icon_connexion.addClass( 'red' );
        icon_connexion.attr( 'data-original-title', 'Websocket: ✘' ).tooltip( 'fixTitle' );
        elect_server();
        return;
    }
    
    if ( webso_con == null ) {
        var e = pot_servers[ server ];
        console.log( 'Connexion try to websocket' );
        var ws_uri = 'ws://' + e.hostname + ':' + e.ws_port + '/ws';
        console.log( 'Connexion to websocket: ' + ws_uri );
        webso_con = new WebSocket( ws_uri );
        icon_connexion.tooltip( { title: 'Connexion to websocket in progress' } );
        webso_con.onopen = function() {
            console.log( 'Connection open!' );
            // We remove the red from the icon so it's back to black
            icon_connexion.removeClass( 'red' );
            icon_connexion.attr( 'data-original-title', 'Websocket: ✔' ).tooltip( 'fixTitle' );
        };
        
        webso_con.onerror = function() {
            webso_con = null;
            // Put the icon for connexion in red
            icon_connexion.addClass( 'red' );
            icon_connexion.attr( 'data-original-title', 'Websocket: ✘' ).tooltip( 'fixTitle' );
            console.log( 'Websocket connection error to ' + ws_uri );
            server = null;
            // We got a problem, reelect a new server
            elect_server();
        };
        
        webso_con.onclose = function() {
            webso_con = null;
            // Put the icon for connexion in red
            icon_connexion.addClass( 'red' );
            icon_connexion.attr( 'data-original-title', 'Websocket: ✘' ).tooltip( 'fixTitle' );
            console.error( 'Wesocket connection error to ' + ws_uri );
            server = null;
            // A problem? let's look at a new server to load from
            elect_server();
        };
        
        webso_con.onmessage = function( e ) {
            console.log( "Socket message:", e.data );
            // Load the host update as a json dict
            var oraw = JSON.parse( e.data );
            if ( oraw.channel != 'gossip' ) {
                console.log( 'Unmanaged websocket message ' + oraw );
                return;
            }
            
            var o = oraw.payload;
            
            var nuuid = o.uuid;
            // Delete the previously add host
            nodes     = $.grep( nodes, function( h ) {
                return h.uuid != nuuid;
            } );
            // Save this host in the list :)
            var n     = new Node( o );
            nodes.push( n );
            // Now generate the doc string from our new host
            var s = generate_host_list_entry( o );
            // Delete the previous li for this node
            console.debug( 'Removing previous node entry:' + nuuid );
            $( '#' + nuuid ).remove();
            // ok add new the one
            $( s ).appendTo( $( '#nodes > ul' ) );
            // resort and hide if need
            apply_filters();
            sort_lists();
            update_counts();
            // If it was the selected, update the detail panel
            console.debug( 'SELECTED ' + selected + ' AND ' + nuuid );
            if ( nuuid == selected ) {
                detail( 'node', nuuid );
            }
        };
    }
}

setInterval( do_webso_connect, 1000 );

$( function() {
    do_webso_connect();
} );


