'use strict';

// Run eslint as part of normal testing
var paths,
	lint = require( 'mocha-eslint' );

paths = [
	'src/**/*.js',
	'bin/**/*.js',
	'test/**/*.js'
];

// Run the tests
lint( paths );
