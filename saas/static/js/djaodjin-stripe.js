// These are the function to interact with the Stripe payment processor.

function initBankProcessor(bankForm, stripePubKey) {

	var submitButton = bankForm.find('[type="submit"]');

	/* Implementation Note:
	   As an inner functions because we use *bankForm* and *stripePubKey*
	   within. */
	function stripeResponseHandler(status, response) {
		if (response.error) {
			// show the errors on the form
			showMessages([response.error.message], "danger");
			submitButton.removeAttr("disabled");
		} else {
			// token contains id, etc.
			var token = response['id'];
			// insert the token into the form so it gets submitted to the server
			bankForm.append(
			"<input type='hidden' name='stripeToken' value='" + token + "'/>");
			// and submit
			bankForm.get(0).submit();
		}
	}

	function stripeCreateToken(event) {
		// disable the submit button to prevent repeated clicks
		submitButton.attr("disabled", "disabled");
		var valid = true
		var error_messages = ""

		var country = bankForm.find("#country").val()
		if( country == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Country"
			bankForm.find("#row-country").addClass('has-error');
			valid = false
		}

		/* BE CAREFULL: Do not add name="" to these <input> nodes,
		   else they will hit our server and break PCI compliance. */
		var accountNumber = bankForm.find("#account-number").val()
		if(!Stripe.bankAccount.validateAccountNumber(accountNumber, country)) {
			if( error_messages ) error_messages += ", "
			error_messages += "Account Number"
			bankForm.find("#row-account-number").addClass('has-error');
			valid = false
		}
		var routingNumber = bankForm.find("#routing-number").val()
		if(!Stripe.bankAccount.validateRoutingNumber(routingNumber, country)) {
			if( error_messages ) error_messages += ", "
			error_messages += "Routing Number"
			bankForm.find("#row-routing-number").addClass('has-error');
			valid = false
		}
		if( error_messages ) {
			error_messages += " field(s) cannot be empty."
		}
		if( valid ) {
			// this identifies your website in the createToken call below
			Stripe.setPublishableKey(stripePubKey);
			Stripe.bankAccount.createToken({
				country: country,
				routingNumber: routingNumber,
				accountNumber: accountNumber
			}, stripeResponseHandler);
		} else {
			showMessages([error_messages], "danger");
			submitButton.removeAttr("disabled");
		}
		// prevent the form from submitting with the default action
		return false;
	}
	bankForm.submit(stripeCreateToken);
}


var Card = function(urls) {
    this.urls = urls;
};


Card.prototype.query = function() {
    var self = this;
    $.get(self.urls.saas_api_card, function(result) {
        $("#last4").text(result.data.last4);
        $("#exp_date").text(result.data.exp_date);
    }).fail(function() {
        $("#last4").text("Err");
        $("#exp_date").text("Err");
    });
};


function initCardProcessor(cardForm, stripePubKey) {
    
    /* Retrieve card information from processor if available. */

	var submitButton = cardForm.find('[type="submit"]');

	/* Implementation Note:
	   As an inner function because we use *stripePubKey* within. */

	function stripeResponseHandler(status, response) {
		if (response.error) {
			// show the errors on the form
			showMessages([response.error.message], "danger");
			submitButton.removeAttr("disabled");
		} else {
			// token contains id, last4, and card type
			var token = response['id'];
			// insert the token into the form so it gets submitted to the server
			cardForm.append("<input type='hidden' name='stripeToken' value='" + token + "'/>");
			// and submit
			cardForm.get(0).submit();
		}
	}

	function stripeCreateToken(event) {
		// disable the submit button to prevent repeated clicks
		submitButton.attr("disabled", "disabled");
		var valid = true
		var error_messages = ""

		if( !cardForm.find("#card-use").is(':visible') ) {
			cardForm.get(0).submit();
			return;
		}

		/* BE CAREFULL: Do not add name="" to these <input> nodes,
		   else they will hit our server and break PCI compliance. */
		var number = cardForm.find("#card-number").val()
		if( number == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Card Number"
			cardForm.find("#row-number").addClass('has-error');
			valid = false
		}
		var cvc = cardForm.find("#card-cvc").val()
		if( cvc == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Card Security Code"
			cardForm.find("#row-cvc").addClass('has-error');
			valid = false
		}
		var exp_month = cardForm.find("#card-exp-month").val()
		var exp_year = cardForm.find("#card-exp-year").val()
		if( exp_month == "" || exp_year == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Expiration"
			cardForm.find("#row-exp").addClass('has-error');
			valid = false
		}

		/* These are OK to forward to our server. */
		var name = cardForm.find("[name='card_name']").val()
		if( name == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Card Holder"
			cardForm.find("#row-name").addClass('has-error');
			valid = false
		}
		var address_line1 = cardForm.find("[name='card_address_line1']").val()
		if( address_line1 == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Street"
			cardForm.find("#row-address-line1").addClass('has-error');
			valid = false
		}
		var address_city = cardForm.find("[name='card_city']").val()
		if( address_city == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "City"
			cardForm.find("#row-city").addClass('has-error');
			valid = false
		}
		var address_state = cardForm.find("[name='card_address_state']").val()
		if( address_state == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "State"
			cardForm.find("#row-address-state").addClass('has-error');
			valid = false
		}
		var address_zip = cardForm.find("[name='card_address_zip']").val()
		if( address_zip == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Zip"
			cardForm.find("#row-address-zip").addClass('has-error');
			valid = false
		}
		var address_country = cardForm.find("[name='card_address_country']").val()
		if( address_country == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Country"
			cardForm.find("#div_id_card_address_country").addClass('has-error');
			valid = false
		}
		if( error_messages ) {
			error_messages += " field(s) cannot be empty."
		}
		if( valid ) {
			// this identifies your website in the createToken call below
			Stripe.setPublishableKey(stripePubKey);
			Stripe.createToken({
				number: cardForm.find("#card-number").val(),
				cvc: cardForm.find("#card-cvc").val(),
				exp_month: cardForm.find("#card-exp-month").val(),
				exp_year: cardForm.find("#card-exp-year").val(),
				name: name,
				address_line1: address_line1,
				address_city: address_city,
				address_state: address_state,
				address_zip: address_zip,
				address_country: address_country
			}, stripeResponseHandler);
		} else {
			showMessages([error_messages], "danger");
			submitButton.removeAttr("disabled");
		}
		// prevent the form from submitting with the default action
		return false;
	}

	cardForm.submit(stripeCreateToken);
}
