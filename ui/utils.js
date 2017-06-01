// Add a way to shuffle an array
Array.prototype.shuffle = function() {
    var i = this.length,
        j,
        temp;
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

if ( typeof String.prototype.endsWith != 'function' ) {
    String.prototype.endsWith = function( suffix ) {
        return this.indexOf( suffix, this.length - suffix.length ) !== -1;
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
        lines    : 17, // The number of lines to draw
        length   : 16, // The length of each line
        width    : 4, // The line thickness
        radius   : 13, // The radius of the inner circle
        corners  : 1, // Corner roundness (0..1)
        rotate   : 0, // The rotation offset
        direction: 1, // 1: clockwise, -1: counterclockwise
        color    : '#33000', // #rgb or #rrggbb or array of colors
        speed    : 1, // Rounds per second
        trail    : 66, // Afterglow percentage
        shadow   : true, // Whether to render a shadow
        hwaccel  : true, // Whether to use hardware acceleration
        className: 'spinner', // The CSS class to assign to the spinner
        zIndex   : 2e9, // The z-index (defaults to 2000000000)
        top      : '100px', // Top position relative to parent
        left     : '50%' // Left position relative to parent
    };
    var target  = $( place );
    var spinner = new Spinner( opts ).spin();
    target.append( spinner.el );
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
