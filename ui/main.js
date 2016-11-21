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

// dict.values()
function dict_get_values( d ) {
    var r = [];
    $.each( d, function( _idx, e ) {
        r.push( e );
    } );
    return r;
}

var __templates_cache = {};
function get_template( tpl_name ) {
    var tpl = __templates_cache[ tpl_name ];
    if ( typeof tpl == 'undefined' ) {
        tpl = $( '#' + tpl_name ).html();
        Mustache.parse( tpl );
        __templates_cache[ tpl_name ] = tpl;
    }
    return tpl;
}


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

/**************************************
 Server Elections
 *************************************/

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
var server   = null;
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
    var ws_port      = port + 1;
    pot_servers[ s ] = {
        'state':   'pending',
        'uri':     s,
        port:      port,
        ws_port:   ws_port,
        hostname:  hostname,
        'elected': false
    };
} );


function update_connections_view() {
    var ul              = $( '#connections-ul' );
    var connections_tpl = get_template( 'tpl-connections-list' );
    // get connections but as list for mustache
    var connections     = dict_get_values( pot_servers );
    var s_connections   = Mustache.render( connections_tpl, { connections: connections } );
    ul.html( s_connections );
}


$( function() {
    update_connections_view();
} );


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
                update_connections_view();
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
                update_connections_view();
            } );
    } );
}

elect_server();


// Main structure to put nodes
var nodes    = [];
var selected = '';


/***********************************************************
 *                         Node                            *
 ***********************************************************/

var __Node_properties = [ 'uuid', 'addr', 'checks', 'incarnation', 'name', 'port', 'state', 'tags' ];  // to copy from gossip
function Node( gossip_entry ) {
    this.update( gossip_entry );
    console.debug( this.tostr() );
}


Node.prototype.update = function( gossip_entry ) {
    for ( var i = 0; i < __Node_properties.length; i++ ) {
        var k     = __Node_properties[ i ];
        this[ k ] = gossip_entry[ k ];
    }
};


Node.prototype.tostr = function() {
    console.log( this );
    var s = 'Node:: ';
    for ( var i = 0; i < __Node_properties.length; i++ ) {
        var k = __Node_properties[ i ];
        s += ' [' + k + '=' + this[ k ] + ']';
    }
    return s;
};


function load_nodes() {
    add_spinner( '#nodes' );
    var now = new Date().getTime();
    $.getJSON( "http://" + server + "/agent/members?_t=" + now, function( data ) {
        // First put all nodes into our list
        $.each( data, function( key, val ) {
            var n = new Node( val );
            console.debug( n.tostr() );
            nodes.push( n );
        } );
        refresh_nodes();
    } );
}


// Hide others main part, update menu and show the one desired
function show_main_part( part ) {
    // Hide
    $( '#list-left > .main-part' ).hide();
    
    // clean menu
    $( '#menu .menu-a' ).removeClass( 'active' );
    
    // Show main part
    $( '#' + part ).show();
    
    // and menu one
    $( '#' + part + '-btn' ).addClass( 'active' );
    
}


// Count the number of node and service, and update the btn badges
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
    var reg   = $( "#filter-value" ).val();
    var state = $( "#filter-state" ).val();
    
    var lis = $( '#' + p + ' > ul > li' );
    
    lis.each( function() {
        var li = $( this );
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
        
        // We must match both name/tag and state
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
    
    $( "#filter-value" ).bind( 'input', function() {
        apply_filters();
    } );
    
    $( "#filter-state" ).on( 'change', function() {
        apply_filters();
    } );
    
    show_main_part( 'nodes' );
    
    var help_text = [ 'Nodes:',
                      '<ul>',
                      '<li>string   => lookup by the node name</li>',
                      '<li><b>t:</b>string => lookup by tag name</li>',
                      '</ul>'
    ].join( '\n' );
    
    $( '#filter-help' ).popover( {
        html:    true,
        content: help_text
    } );
    
} );


// Generate a LI string with the host information
function generate_host_list_entry( node ) {
    var node_bloc_tpl = get_template( 'tpl-node-bloc' );
    var s             = Mustache.to_html( node_bloc_tpl, node );
    return s;
    
}


// Go with all nodes and print them on the list elements
function refresh_nodes() {
    var items = [];
    for ( var i = 0; i < nodes.length; i++ ) {
        var n = nodes[ i ];
        var s = generate_host_list_entry( n );
        items.push( s );
    }
    
    $( "#nodes" ).html( '' );
    var ul = $( "<ul/>", {
        "class": "node-list",
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
function show_detail( nuuid ) {
    // First clean detail parts
    clean_detail();
    update_detail( nuuid );
    open_right_panel();
}


// Clean all detail content from old content
function clean_detail() {
    $( '#detail-header' ).html( '' );
    $( '#detail-checks' ).html( '' );
    $( '#detail-collectors' ).html( '' );
    $( '#detail-detectors' ).html( '' );
    $( '#detail-information' ).html( '' );
    show_detail_part( 'checks' ); // show checks by default
}


// only show a specific detail part (like checks)
function show_detail_part( part ) {
    // first hide all
    $( '#detail .detail-part' ).hide();
    $( '#detail-' + part ).show();
}


function update_detail( nuuid ) {
    // We got a click, tag the selected element
    selected = nuuid;
    
    var node = find_node( nuuid );
    if ( node == null ) {
        return;
    }
    var now = new Date().getTime();
    
    // Node detail + checks
    $.getJSON( "http://" + server + "/agent/state/" + nuuid + '?_t=' + now, function( data ) {
        // first header
        var detail_header_tpl = get_template( 'tpl-detail-header' );
        var s_detail_header   = Mustache.to_html( detail_header_tpl, node );
        $( '#detail-header' ).html( s_detail_header );
        
        // now checks
        var detail_checks_tpl = get_template( 'tpl-detail-checks' );
        var s_detail_checks   = Mustache.to_html( detail_checks_tpl, { 'checks': dict_get_values( data.checks ) } );
        $( '#detail-checks' ).html( s_detail_checks );
        
    } );
    
    // Agent informations + information
    $.getJSON( 'http://' + node.addr + ':' + node.port + '/agent/info?_t=' + now, function( data ) {
        // first agent information
        var detail_information_tpl = get_template( 'tpl-detail-information' );
        var s_detail_information   = Mustache.to_html( detail_information_tpl, data );
        $( '#detail-information' ).html( s_detail_information );
        
        // and collectors basic information (more information with metrics will need more additional calls)
        var detail_collectors_tpl = get_template( 'tpl-detail-collectors' );
        var s_detail_collectors   = Mustache.to_html( detail_collectors_tpl, { 'collectors': dict_get_values( data.collectors ) } );
        $( '#detail-collectors' ).html( s_detail_collectors );
    } );
    
    // Detectors informations
    $.getJSON( 'http://' + node.addr + ':' + node.port + '/agent/detectors/?_t=' + now, function( data ) {
        // first agent information
        var detail_detectors_tpl = get_template( 'tpl-detail-detectors' );
        var s_detail_detectors   = Mustache.to_html( detail_detectors_tpl, { 'detectors': data } );
        $( '#detail-detectors' ).html( s_detail_detectors );
    } );
    
}

var __is_panel_open = false;
function toggle_right_panel() {
    if ( __is_panel_open ) {
        close_right_panel();
    } else {
        open_right_panel();
    }
}


// Force a close of the right panel
function close_right_panel() {
    // if already close, bail out
    if ( !__is_panel_open ) {
        return;
    }
    __is_panel_open = false;
    $( '#part-right' ).removeClass( 'expanded' );
}


// Force an open of the right panel
function open_right_panel() {
    // if already open, bail out
    if ( __is_panel_open ) {
        return;
    }
    __is_panel_open = true;
    $( '#part-right' ).addClass( 'expanded' );
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
    var icon_connection = $( '#icon-connection' );
    if ( server == null ) {
        icon_connection.addClass( 'red' );
        icon_connection.attr( 'data-original-title', 'Websocket: ✘' ).tooltip( 'fixTitle' );
        elect_server();
        return;
    }
    
    if ( webso_con == null ) {
        var e = pot_servers[ server ];
        console.log( 'Connexion try to websocket' );
        var ws_uri = 'ws://' + e.hostname + ':' + e.ws_port + '/ws';
        console.log( 'Connexion to websocket: ' + ws_uri );
        webso_con = new WebSocket( ws_uri );
        icon_connection.tooltip( { title: 'Connexion to websocket in progress' } );
        webso_con.onopen = function() {
            console.log( 'Connection open!' );
            // We remove the red from the icon so it's back to black
            icon_connection.removeClass( 'red' );
            icon_connection.attr( 'data-original-title', 'Websocket: ✔' ).tooltip( 'fixTitle' );
        };
        
        webso_con.onerror = function() {
            webso_con = null;
            // Put the icon for connection in red
            icon_connection.addClass( 'red' );
            icon_connection.attr( 'data-original-title', 'Websocket: ✘' ).tooltip( 'fixTitle' );
            console.log( 'Websocket connection error to ' + ws_uri );
            server = null;
            // We got a problem, reelect a new server
            elect_server();
        };
        
        webso_con.onclose = function() {
            webso_con = null;
            // Put the icon for connection in red
            icon_connection.addClass( 'red' );
            icon_connection.attr( 'data-original-title', 'Websocket: ✘' ).tooltip( 'fixTitle' );
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
            
            var n = find_node( nuuid );
            if ( n != null ) {  // was existing
                n.update( o );
            } else { // ok a new one
                // Save this host in the list :)
                n = new Node( o );
                nodes.push( n );
            }
            
            // Now generate the doc string from our new host
            var s = generate_host_list_entry( n );
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
                update_detail( nuuid );
            }
        };
    }
}


setInterval( do_webso_connect, 1000 );


$( function() {
    do_webso_connect();
} );


/*************************************************
 EVAL (yes it's bad but soooo good)
 *************************************************/
function evaluate_expr() {
    var expr = $( '#evaluations-rule-input' ).val();
    console.log( 'EXPRESSION: ' + expr );
    var expr64 = btoa( expr );
    
    var postdata = { 'expr': expr64 };
    
    var now = new Date().getTime();
    $( '#evaluations-result' ).html( '' );
    $.ajax( {
        type:    "POST",
        url:     'http://' + server + '/agent/evaluator/eval?_t=' + now,
        data:    postdata,
        success: function( data ) {
            console.log( 'EVAL RETURN:' );
            console.log( data );
            $( '#evaluations-result' ).html( data.toString() );
        }
    } );
}

function get_available_functions() {
    var now = new Date().getTime();
    // Get available functions from the server
    $.getJSON( 'http://' + server + '/agent/evaluator/list?_t=' + now, function( data ) {
        // first agent information
        var tpl = get_template( 'tpl-evaluations-available-functions' );
        console.log( 'FUNCTIONS' );
        console.log( data );
        for ( var i = 0; i < data.length; i++ ) {
            var e = data[ i ];
            console.log( 'ARG' );
            console.log( e );
            var prototype = e.prototype;
            if ( prototype != null ) {
                var _parts = [];
                for ( var j = 0; j < prototype.length; j++ ) {
                    var p        = prototype[ j ];
                    var arg_name = p[ 0 ];
                    var arg_def  = p[ 1 ];
                    if ( arg_def == '__NO_DEFAULT__' ) {
                        _parts.push( arg_name );
                    } else { // really with default value, set it
                        _parts.push( arg_name + '=' + arg_def );
                    }
                }
                e.prototype_cleaned = _parts;
            } else {
                e.prototype_cleaned = null;
            }
        }
        var s = Mustache.to_html( tpl, { 'functions': data } );
        $( '#evaluations-available-functions' ).html( s );
        
    } );
    
}
