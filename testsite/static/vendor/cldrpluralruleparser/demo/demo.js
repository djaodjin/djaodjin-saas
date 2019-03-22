/*globals pluralRuleParser, jQuery, document */
(function($) {
	"use strict";

	$.getJSON('../node_modules/cldr-data/supplemental/plurals.json', init);

	var pluraldata = {};

	function init(plurals) {
		pluraldata = plurals;
		$('#input-language, #input-number').on('change', changeHandler);
		changeHandler();
	}

	function changeHandler() {
		calculate(pluraldata, {
			locale: $('#input-language').val(),
			number: $('#input-number').val()
		});
	}

	function calculate(pluraldata, options) {
		var pluralRules, rule, result, $resultdiv;

		$('.result').empty();
		pluralRules = pluraldata.supplemental['plurals-type-cardinal'][options.locale];
		if (!pluralRules) {
			$('.result').append($('<div>')
				.addClass('alert alert-error')
				.text('No plural rules found')
			);
		}
		for (var ruleName in pluralRules) {
			rule = pluralRules[ruleName];
			$resultdiv = $('<div>')
				.addClass('alert alert-error')
				.html(ruleName.split('-').pop() + ': ' + rule);

			if (!result) {
				result = pluralRuleParser(rule + '', options.number);
				if (result) {
					$resultdiv.removeClass('alert-error').addClass('alert-success');
				}
			}

			$('.result').append($resultdiv);

		}
	}

}(jQuery));