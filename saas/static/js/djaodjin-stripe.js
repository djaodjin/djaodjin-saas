/* Functionality to interact with the Stripe payment processor.
 */
(function ($) {
    "use strict";

        /** Augment a <form> to request a token from a bank account, then submit
        the form with that token.

        usage:
            $("payment-form").bank({stripePubKey: *YourStripePublicKey*});

        HTML requirements:
            <form>
              <!-- BE CAREFULL: Do not add name="" to the #account-number
                   and #routing-number input nodes, else values will hit
                   the server and break PCI compliance. -->
              <div class="form-group">
                <input id="account-number" type="text" autocomplete="off" />
              </div>
              <div class="form-group">
                <input id="routing-number" type="text" autocomplete="off" />
              </div>
              <div class="form-group">
                <input name="country" type="text" />
              </div>
            </form>
     */
    function Bank(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    Bank.prototype = {
        init: function () {
            var self = this;
            self.element.submit(
                function (event) { return self.stripeCreateToken(event); });
        },

        stripeResponseHandler: function(status, response) {
            var self = this;
            var submitButton = self.element.find("[type='submit']");
            if (response.error) {
                // show the errors on the form
                showMessages([response.error.message], "error");
                submitButton.removeAttr("disabled");
            } else {
                // token contains id, etc.
                var token = response.id;
                // insert the token into the form so it gets submitted
                // to the server.
                self.element.append(
                    "<input type='hidden' name='stripeToken' value='" + token + "'/>");
                // and submit
                self.element.get(0).submit();
            }
        },

        stripeCreateToken: function(event) {
            var self = this;
            var submitButton = self.element.find("[type='submit']");
            // disable the submit button to prevent repeated clicks
            submitButton.attr("disabled", "disabled");
            var valid = true;
            var errorMessages = "";

            var countryElement = self.element.find("name=['country']");
            var country = countryElement.val();
            if( country === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Country";
                countryElement.parents(".form-group").addClass("has-error");
                valid = false;
            }

            /* BE CAREFULL: Do not add name="" to these <input> nodes,
               else they will hit our server and break PCI compliance. */
            var accountNumberElement = self.element.find("#account-number");
            var accountNumber = accountNumberElement.val();
            if(!Stripe.bankAccount.validateAccountNumber(accountNumber, country)) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Account Number";
                accountNumberElement.parents(".form-group").addClass("has-error");
                valid = false;
            }
            var routingNumberElement = self.element.find("#routing-number");
            var routingNumber = routingNumberElement.val();
            if(!Stripe.bankAccount.validateRoutingNumber(routingNumber, country)) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Routing Number";
                routingNumberElement.parents(
                    ".form-group").addClass("has-error");
                valid = false;
            }
            if( errorMessages ) {
                errorMessages += " field(s) cannot be empty.";
            }
            if( valid ) {
                // this identifies your website in the createToken call below
                Stripe.setPublishableKey(self.options.stripePubKey);
                Stripe.bankAccount.createToken({
                    country: country,
                    routingNumber: routingNumber,
                    accountNumber: accountNumber
                }, function(status, response) {
                    self.stripeResponseHandler(status, response);
                });
            } else {
                showMessages([errorMessages], "error");
                submitButton.removeAttr("disabled");
            }
            // prevent the form from submitting with the default action
            return false;
        }
    };

    $.fn.bank = function(options) {
        var opts = $.extend( {}, $.fn.bank.defaults, options );
        return new Bank($(this), opts);
    };

    $.fn.bank.defaults = {
        stripePubKey: null
    };

    /** Augment a <form> to request a token from a credit card, then submit
        the form with that token.

        usage:
            $("payment-form").card({stripePubKey: *YourStripePublicKey*});

        HTML requirements:
            <form>
              <div id="card-use">
              <!-- BE CAREFULL: Do not add name="" to the #card-number,
                   #card-cvc, #card-exp-month, #card-exp-year input nodes,
                   else values will hit the server and break PCI compliance. -->
                <div class="form-group">
                  <input id="card-number" type="text" autocomplete="off" />
                </div>
                <div class="form-group">
                  <input id="card-cvc" type="text" autocomplete="off" />
                </div>
                <div class="form-group">
                  <input id="card-exp-month" type="text" autocomplete="off" />
                </div>
                <div class="form-group">
                  <input id="card-exp-year" type="text" autocomplete="off" />
                </div>
                <div class="form-group">
                  <input name="card_name" type="text" />
                </div>
                <div class="form-group">
                  <input name="card_address_line1" type="text" />
                </div>
                <div class="form-group">
                  <input name="card_city" type="text" />
                </div>
                <div class="form-group">
                  <input name="region" type="text" />
                </div>
                <div class="form-group">
                  <input name="card_address_zip" type="text" />
                </div>
                <div class="form-group">
                  <input name="country" type="text" />
                </div>
              </div>
            </form>
     */
    function Card(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    Card.prototype = {
        init: function () {
            var self = this;
            self.element.submit(
                function (event) { return self.stripeCreateToken(event); });
        },

        stripeResponseHandler: function(status, response) {
            var self = this;
            var submitButton = self.element.find("[type='submit']");
            if (response.error) {
                // show the errors on the form
                showMessages([response.error.message], "error");
                submitButton.removeAttr("disabled");
            } else {
                // token contains id, last4, and card type
                var token = response.id;
                // insert the token into the form so it gets submitted to the server
                self.element.append("<input type='hidden' name='stripeToken' value='" + token + "'/>");
                // and submit
                self.element.get(0).submit();
            }
        },

        stripeCreateToken: function(event) {
            // disable the submit button to prevent repeated clicks
            event.preventDefault();
            var self = this;
            var submitButton = self.element.find("[type='submit']");
            submitButton.attr("disabled", "disabled");
            var valid = true;
            var errorMessages = "";

            var cardUse = self.element.find("#card-use");
            if( !cardUse.is(":visible") ) {
                return self.element.get(0).submit(event);
            }

            /* BE CAREFULL: Do not add name="" to these <input> nodes,
               else they will hit our server and break PCI compliance. */
            var numberElement = cardUse.find("#card-number");
            var number = numberElement.val();
            if( number === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Card Number";
                numberElement.parents(".form-group").addClass("has-error");
                valid = false;
            }
            var cvcElement = cardUse.find("#card-cvc");
            var cvc = cvcElement.val();
            if( cvc === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Card Security Code";
                cvcElement.parents(".form-group").addClass("has-error");
                valid = false;
            }
            var expMonthElement = cardUse.find("#card-exp-month");
            var expYearElement = cardUse.find("#card-exp-year");
            var expMonth = expMonthElement.val();
            var expYear = expYearElement.val();
            if( expMonth === "" || expYear === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Expiration";
                expMonthElement.parents(".form-group").addClass("has-error");
                expYearElement.parents(".form-group").addClass("has-error");
                valid = false;
            }

            /* These are OK to forward to our server. */
            var nameElement = cardUse.find("[name='card_name']");
            var name = nameElement.val();
            if( name === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Card Holder";
                nameElement.parents(".form-group").addClass("has-error");
                valid = false;
            }
            var addressLine1Element = cardUse.find("[name='card_address_line1']");
            var addressLine1 = addressLine1Element.val();
            if( addressLine1 === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Street";
                addressLine1Element.parents(
                    ".form-group").addClass("has-error");
                valid = false;
            }
            var addressCityElement = cardUse.find("[name='card_city']");
            var addressCity = addressCityElement.val();
            if( addressCity === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "City";
                addressCityElement.parents(".form-group").addClass("has-error");
                valid = false;
            }
            var addressStateElement = cardUse.find("[name='region']");
            var addressState = addressStateElement.val();
            if( addressState === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "State/Province";
                addressStateElement.parents(
                    ".form-group").addClass("has-error");
                valid = false;
            }
            var addressZipElement = cardUse.find("[name='card_address_zip']");
            var addressZip = addressZipElement.val();
            if( addressZip === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Zip";
                addressZipElement.parents(".form-group").addClass("has-error");
                valid = false;
            }
            var addressCountryElement = cardUse.find("[name='country']");
            var addressCountry = addressCountryElement.val();
            if( addressCountry === "" ) {
                if( errorMessages ) { errorMessages += ", "; }
                errorMessages += "Country";
                addressCountryElement.parents(
                    ".form-group").addClass("has-error");
                valid = false;
            }
            if( errorMessages ) {
                errorMessages += " field(s) cannot be empty.";
            }
            if( valid ) {
                // this identifies your website in the createToken call below
                Stripe.setPublishableKey(self.options.stripePubKey);
                Stripe.createToken({
                    number: number,
                    cvc: cvc,
                    exp_month: expMonth,
                    exp_year: expYear,
                    name: name,
                    address_line1: addressLine1,
                    address_city: addressCity,
                    address_state: addressState,
                    address_zip: addressZip,
                    address_country: addressCountry
                }, function(status, response) {
                    self.stripeResponseHandler(status, response);
                });
            } else {
                showMessages([errorMessages], "error");
                submitButton.removeAttr("disabled");
            }
            // prevent the form from submitting with the default action
            return false;
        }
    };

    $.fn.card = function(options) {
        var opts = $.extend( {}, $.fn.card.defaults, options );
        return new Card($(this), opts);
    };

    $.fn.card.defaults = {
        stripePubKey: null
    };


})(jQuery);
