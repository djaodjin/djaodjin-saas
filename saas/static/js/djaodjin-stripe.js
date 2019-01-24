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
            var accountNumberElement = self.element.find("#account-number");
            if( accountNumberElement.length > 0 ) {
                self.element.submit(
                    function (event) { return self.stripeCreateToken(event); });
            }
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
            event.preventDefault();
            var self = this;
            var submitButton = self.element.find("[type='submit']");
            // disable the submit button to prevent repeated clicks
            submitButton.attr("disabled", "disabled");
            var valid = true;
            var errorMessages = "";

            var countryElement = self.element.find("[name='country']");
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
              <div class="last4"></div>
              <div class="exp_date"></div>
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


})(jQuery);
