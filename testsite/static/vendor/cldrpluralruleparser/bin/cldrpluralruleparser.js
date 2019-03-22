#!/usr/bin/env node

var parser = require(__dirname + '/../src/CLDRPluralRuleParser.js');
if (process.argv.length < 3) {
    process.stdout.write("Please provide the rule and a number to test\n");
    process.stdout.write("Example:\n");
    process.stdout.write("cldrpluralruleparser 'v = 0 and n != 0..10 and n % 10 = 0' 20\n");
} else {
    var result = parser(process.argv[2], process.argv[3]);
    process.stdout.write(result);
    process.stdout.write("\n");
}