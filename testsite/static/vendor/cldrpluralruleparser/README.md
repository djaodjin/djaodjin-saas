CLDR Plural Rule Evaluator
==========================
Find out the plural form for a given number in a language
[![NPM version](https://badge.fury.io/js/cldrpluralruleparser.svg)](https://www.npmjs.org/package/cldrpluralruleparser)
[![Build Status](https://travis-ci.org/santhoshtr/CLDRPluralRuleParser.svg?branch=master)](https://travis-ci.org/santhoshtr/CLDRPluralRuleParser)

Quick start
----------

```bash
git clone https://github.com/santhoshtr/CLDRPluralRuleParser.git
npm install
```

Documentation
----------

Unlike English, for many languages, the plural forms are just not 2 forms.
If you look at the <a href="http://unicode.org/repos/cldr-tmp/trunk/diff/supplemental/language_plural_rules.html#pl">CLDR plural rules table</a>
you can easily understand this. The rules are defined in a particular syntax
(an eg: for Russian, the plural few is applied when the rule
"`n mod 10 in 2..4 and n mod 100 not in 12..14;`" is passed).

This tool is a demonstration of a [javascript parser](./src/CLDRPluralRuleParser.js)
for the plural rules in that syntax.

For a given number in a language, this tool tells which plural form it belongs.
The plural rules are taken from the CLDR  data file

Example
--------
Demonstration of the javascript parser at:
http://thottingal.in/projects/js/plural/demo/

Test
----
```npm test```

Node module
-----------
This is also available as a node module. You can install it using:

`npm install cldrpluralruleparser`

Once installed it provides a command line utility named cldrpluralruleparser too.
```
$ cldrpluralruleparser 'n is 1' 0
false
```


