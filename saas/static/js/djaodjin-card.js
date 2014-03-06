// These are the function to interact with the Stripe payment processor.

function stripeResponseHandler(status, response) {
	if (response.error) {
		// show the errors on the form
		$("#messages").removeClass('hidden');
		$("#messages ul").append(
		"<li>" + response.error.message + "</li>");
		$(".payment-submit").removeAttr("disabled");
	} else {
		var form$ = $("#payment-form");
		// token contains id, last4, and card type
		var token = response['id'];
		// insert the token into the form so it gets submitted to the server
		form$.append("<input type='hidden' name='stripeToken' value='" + token + "'/>");
		// and submit
		form$.get(0).submit();
	}
}

function initCardProcessor(stripePubKey) {

	/* Implementation Note:
	   As an inner function because we use *stripePubKey* within. */
	function stripeCreateToken(event) {
		// disable the submit button to prevent repeated clicks
		$(".payment-submit").attr("disabled", "disabled");
		var valid = true
		var error_messages = ""

		/* BE CAREFULL: Do not add name="" to these <input> nodes,
		   else they will hit our server and break PCI compliance. */
		var number = $("#card-number").val()
		if( number == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Card Number"
			$("#row-number").addClass('has-error');
			valid = false
		}
		var cvc = $("#card-cvc").val()
		if( cvc == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Card Security Code"
			$("#row-cvc").addClass('has-error');
			valid = false
		}
		var exp_month = $("#card-exp-month").val()
		var exp_year = $("#card-exp-year").val()
		if( exp_month == "" || exp_year == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Expiration"
			$("#row-exp").addClass('has-error');
			valid = false
		}

		/* These are OK to forward to our server. */
		var name = $("#payment-form [name='card_name']").val()
		if( name == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Card Holder"
			$("#payment-form #row-name").addClass('has-error');
			valid = false
		}
		var address_line1 = $("#payment-form [name='card_address_line1']").val()
		if( address_line1 == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Street"
			$("#payment-form #row-address-line1").addClass('has-error');
			valid = false
		}
		var address_city = $("#payment-form [name='card_city']").val()
		if( address_city == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "City"
			$("#payment-form #row-city").addClass('has-error');
			valid = false
		}
		var address_state = $("#payment-form [name='card_address_state']").val()
		if( address_state == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "State"
			$("#payment-form #row-address-state").addClass('has-error');
			valid = false
		}
		var address_zip = $("#payment-form [name='card_address_zip']").val()
		if( address_zip == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Zip"
			$("#payment-form #row-address-zip").addClass('has-error');
			valid = false
		}
		var address_country = $("#payment-form [name='card_address_country']").val()
		if( address_country == "" ) {
			if( error_messages ) error_messages += ", "
			error_messages += "Country"
			$("#payment-form #div_id_card_address_country").addClass('has-error');
			valid = false
		}
		if( error_messages ) {
			error_messages += " field(s) cannot be empty."
		}
		if( valid ) {
			// this identifies your website in the createToken call below
			Stripe.setPublishableKey(stripePubKey);
			Stripe.createToken({
				number: $("#card-number").val(),
				cvc: $("#card-cvc").val(),
				exp_month: $("#card-exp-month").val(),
				exp_year: $("#card-exp-year").val(),
				name: name,
				address_line1: address_line1,
				address_city: address_city,
				address_state: address_state,
				address_zip: address_zip,
				address_country: address_country
			}, stripeResponseHandler);
		} else {
			$("#messages").removeClass('hidden');
			$("#messages ul").append(
				"<li>" + error_messages + "</li>");
			$(".payment-submit").removeAttr("disabled");
		}
		// prevent the form from submitting with the default action
		return false;
	}

	$('#card-number').payment('formatCardNumber');
	$('#card-number').keyup(function(){
		var cc_type = $.payment.cardType($('#card-number').val());
		if (cc_type == 'visa'){
			$('#visa').css( "opacity", "1" );
		}else if (cc_type == 'mastercard'){
			$('#mastercard').css( "opacity", "1" );
		}else if (cc_type == 'amex'){
			$('#amex').css( "opacity", "1" );
		}else if (cc_type == 'discover'){
			$('#discover').css( "opacity", "1" );
		}else{
			$('#visa').css( "opacity","0.1");
			$('#mastercard').css( "opacity", "0.1" );
			$('#amex').css( "opacity", "0.1" );
			$('#discover').css( "opacity", "0.1" );
		}
	});
	$("#payment-form").submit(stripeCreateToken);
}
