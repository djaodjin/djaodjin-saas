/**
   Functionality related to the cart and checkout of djaodjin-saas.

   These are based on jquery.
 */

/*global location setTimeout jQuery*/
/*global getMetaCSRFToken showMessages*/


(function ($) {
    "use strict";

    /** Add/Remove a ``CartItem`` from the active shopping cart.

        HTML requirements:

        <form id="*plan.slug*">
            <input type="hidden" name="csrfmiddlewaretoken" value="...">
            <button type="submit">*addLabel*</button>
        </form>
     */
    function CartItem(el, options) {
        this.element = $(el);
        this.options = options;
        this.init();
    }

    CartItem.prototype = {
        init: function() {
            var self = this;
            self.item = {};
            var restricted = ["plan",  "option",
                "full_name", "sync_on", "invoice_key"];
            for(var i = 0; i < restricted.length; ++i ) {
                var key = restricted[i];
                if( key in self.options ) {
                    self.item[key] = self.options[key];
                }
            }
            if( self.element.attr('id') ) {
                self.item.plan = self.element.attr('id');
            }
            self.submitBtn = self.element.find("[type='submit']");
            if( self.submitBtn.empty() ) {
                self.submitBtn = self.element;
            }
            self.submitBtn.click(function (event) {
                event.preventDefault();
                if( self.submitBtn.text() == self.options.removeLabel ) {
                    self.remove();
                } else {
                    self.add();
                }
            });
        },

        _getCSRFToken: function() {
            var self = this;
            var crsfNode = self.element.find("[name='csrfmiddlewaretoken']");
            if( crsfNode.length > 0 ) {
                return crsfNode.val();
            }
            return getMetaCSRFToken();
        },

        add: function() {
            var self = this;
            $.ajax({
                type: "POST", // XXX Might still prefer to do PUT on list.
                url: self.options.api_cart,
                beforeSend: function(xhr) {
                    xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                },
                data: JSON.stringify(self.item),
                datatype: "json",
                contentType: "application/json; charset=utf-8",
                success: function(data) {
                    self.submitBtn.text(self.options.removeLabel);
                },
                error: function(resp) {
                    showErrorMessages(resp);
                }
            });
        },

        remove: function(successFunction) {
            var self = this;
            $.ajax({
                type: "DELETE",
                url: self.options.api_cart + "?plan=" + self.item.plan,
                beforeSend: function(xhr) {
                    xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                },
                success: function(data) {
                    self.submitBtn.text(self.options.addLabel);
                }
            });
        }
    };

    $.fn.cartItem = function(options) {
        var opts = $.extend( {}, $.fn.cartItem.defaults, options );
        return this.each(function() {
            $(this).data("cartItem", new CartItem($(this), opts));
        });
    };

    $.fn.cartItem.defaults = {
        addLabel: gettext("Add to Cart"),
        removeLabel: gettext("Remove from Cart"),
        nb_periods: 1,
        api_cart: null
    };


    /** Monitor the state (in-process, declined, etc.) of a ``Charge``

        HTML requirements:

        <... class="charge-status"
             data-charge-done="HTML to display when charge succeeded."
             data-charge-failed="HTML to display when charge failed."
             data-charge-disputed="HTML to display when charge was disputed."
             data-charge-created="HTML to display when charge is in progress.">
        </...>
     */
    function ChargeMonitor(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    ChargeMonitor.prototype = {
        init: function () {
            var self = this;
            if( self.options.initialState === "created" ) {
                self.waitForCompletion();
            }
        },

        waitForCompletion: function() {
            var self = this;
            $.ajax({
                type: "GET",
                url: self.options.saas_api_charge,
                datatype: "json",
                contentType: "application/json; charset=utf-8",
                success: function(data) {
                    if( data.state === "created" ) {
                        setTimeout(function() {
                            self.waitForCompletion(); }, 1000);
                    } else {
                        var statusElement = self.element.find(".charge-status");
                        statusElement.text(
                            statusElement.attr("data-charge-" + data.state));
                    }
                }
            });
        }
    };

    $.fn.chargeMonitor = function(options) {
        var opts = $.extend( {}, $.fn.chargeMonitor.defaults, options );
        return this.each(function() {
            $(this).data("chargeMonitor", new ChargeMonitor($(this), opts));
        });
    };

    $.fn.chargeMonitor.defaults = {
        initialState: "created",
        saas_api_charge: null
    };

    /** Email a receipt for a charge. This behavior is typically associated
        to a button.
     */
    function ChargeEmailReceipt(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    ChargeEmailReceipt.prototype = {
        init: function () {
            var self = this;
            self.state = self.options.initialState;
            self.element.click(function (event) {
                event.preventDefault();
                self.emailReceipt();
            });
        },

        _getCSRFToken: function() {
            var self = this;
            var crsfNode = self.element.find("[name='csrfmiddlewaretoken']");
            if( crsfNode.length > 0 ) {
                return crsfNode.val();
            }
            return getMetaCSRFToken();
        },

        emailReceipt: function() {
            var self = this;
            if( self.state === "created" ) {
                setTimeout(function() {
                    $.ajax({
                        type: "GET",
                        url: self.options.saas_api_charge,
                        datatype: "json",
                        contentType: "application/json; charset=utf-8",
                        success: function(data) {
                            self.state = data.state;
                            self.emailReceipt();
                        }
                    });
                }, 1000);
            } else {
                $.ajax({
                    type: "POST",
                    url: self.options.saas_api_email_charge_receipt,
                    beforeSend: function(xhr) {
                        xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                    },
                    datatype: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data) {
                        showMessages([interpolate(gettext(
                            "A copy of the receipt was sent to %s."),
                            [data.email])], "info");
                    },
                    error: function(resp) {
                        showErrorMessages(resp);
                    }
                });
            }
        }
    };

    $.fn.chargeEmailReceipt = function(options) {
        var opts = $.extend( {}, $.fn.chargeEmailReceipt.defaults, options );
        return new ChargeEmailReceipt($(this), opts);
    };

    $.fn.chargeEmailReceipt.defaults = {
        initialState: "created",
        saas_api_email_charge_receipt: null
    };

    /** Decorate a form to create a refund on a ``ChargeItem``.

        HTML requirements:
        <form>
          <input name="amount">
          <button type="submit"></button>
        </form>
     */
    function Refund(el, options){
        var self = this;
        self.element = $(el);
        self.setOptions(options);
        self.init();
    }

    Refund.prototype = {
        init: function () {
            var self = this;
            var submitButton = self.element.find("[type='submit']");
            // Make sure we unbind the previous handler to avoid double submits
            submitButton.off("click.refund");
            submitButton.on("click.refund", function() {
                return self.submit();
            });
        },

        _getCSRFToken: function() {
            var self = this;
            var crsfNode = self.element.find("[name='csrfmiddlewaretoken']");
            if( crsfNode.length > 0 ) {
                return crsfNode.val();
            }
            return getMetaCSRFToken();
        },

        setOptions: function(opts) {
            var self = this;
            self.options = opts;
            var refundedInput = self.element.find("[name='amount']");
            var availableAmount =
                (self.options.availableAmount / 100).toFixed(2);
            refundedInput.attr("max", availableAmount);
            refundedInput.attr("data-linenum", self.options.linenum);
            refundedInput.val(availableAmount);
        },

        submit: function() {
            var self = this;
            var refundButton = self.options.refundButton;
            var refundedInput = self.element.find("[name='amount']");
            var availableAmount = refundedInput.attr("max");
            var linenum = refundedInput.attr("data-linenum");
            var refundedAmount = refundedInput.val();
            availableAmount = parseInt(
                parseFloat(availableAmount.replace(/[^\d\.]/g, "")) * 100);
            refundedAmount = parseInt(
                parseFloat(refundedAmount.replace(/[^\d\.]/g, "")) * 100);
            if( refundedAmount > availableAmount ) {
                refundedAmount = availableAmount;
            }
            if( refundedAmount > 0 ) {
                refundButton.attr("disabled", "disabled");
                $.ajax({
                    type: "POST",
                    url: self.options.saas_api_charge_refund,
                    beforeSend: function(xhr) {
                        xhr.setRequestHeader(
                            "X-CSRFToken", self._getCSRFToken());
                    },
                    data: JSON.stringify({"lines":
                        [{"num": linenum, "refunded_amount": refundedAmount}]}),
                    datatype: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data) {
                        var message = gettext("Amount refunded.");
                        if( data.responseJSON ) {
                            message = data.responseJSON.detail;
                        }
                        showMessages([message], "info");
                        refundButton.replaceWith(
                            "<em>" + gettext("Refunded") + "</em>");
                    },
                    error: function(resp) {
                        showErrorMessages(resp);
                        refundButton.removeAttr("disabled");
                    }
                });
            }
        }
    };

    $.fn.refund = function(options) {
        var opts = $.extend({}, $.fn.refund.defaults, options);
        return this.each(function() {
            var element = $(this)[0];
            var refund = $.data(element, "refund");
            if( !refund ) {
                var v = $.data(element, "refund", new Refund(element, opts));
            } else {
                refund.setOptions(opts);
            }
        });
    };

    $.fn.refund.defaults = {
        availableAmount: 0,
        linenum: 0,
        saas_api_charge_refund: null,
        refundButton: null
    };

    /** Invoice
     */
    function Invoice(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    Invoice.prototype = {
        init: function () {
            var self = this;

            self.element.find("input:radio").change(function() {
                self.updateTotalAmount();
            });

            self.element.find(".add-seat").click(function(event) {
                event.preventDefault();
                var subscription = $(this).parents("tbody");
                var seatFullname = subscription.find(".seat-fullname");
                var fullname = "";
                if( seatFullname ) {
                    fullname = seatFullname.val();
                    seatFullname.val("");
                } else {
                    var seatFirstName = subscription.find(".seat-first-name");
                    var seatLastName = subscription.find(".seat-last-name");
                    fullname = seatFirstName.val() + ' ' + seatLastName.val();
                    seatFirstName.val("");
                    seatLastName.val("");
                }
                var seatEmail = subscription.find(".seat-email");
                var item = {
                    plan: subscription.attr("data-plan"),
                    full_name: fullname,
                    sync_on: seatEmail.val(),
                    email: seatEmail.val(),
                };
                seatEmail.val("");
                $.ajax({
                    type: "POST", // XXX Might still prefer to do PUT on list.
                    url: self.options.saas_api_cart,
                    beforeSend: function(xhr) {
                      xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                    },
                    data: JSON.stringify(item),
                    datatype: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data, textStatus, jqXHR) {
                        if( jqXHR.status === 201 ) {
                            self.insertLine(data);
                        } else {
                            self.updateLine(data);
                        }
                    },
                    error: function(resp) {
                        showErrorMessages(resp);
                    }
                });
                return false;
            });

            self.element.find(".seat-upload-file").click(function(event) {
                var file = $(this).parents("td").find(".seat-file");
                var plan = $(this).parents("tbody").attr("data-plan");
                if (file.get(0).files.length > 0) {
                    var formData = new FormData();
                    formData.append("file", file.get(0).files[0]);
                    $.ajax({
                        type: "POST",
                        url: "/api/cart/" + plan + "/upload/",
                        beforeSend: function(xhr) {
                            xhr.setRequestHeader(
                                "X-CSRFToken", self._getCSRFToken());
                        },
                        data: formData,
                        processData: false,
                        contentType: false,
                        success: function(data) {
                            for (var i in data.created) {
                                self.insertLine(data.created[i]);
                            }
                            for (var i in data.updated) {
                                self.updateLine(data.updated[i]);
                            }
                            file.val("").change();
                        },
                        error: function(resp) {
                            showErrorMessages(resp);
                        }
                    });
                }
            });

            self.element.find(".seat-file").change(function(event) {
                self.updateUploadButtonVisibility($(this));
            }).each(function() {
                self.updateUploadButtonVisibility($(this));
            });

            if(window.FormData === undefined) {
                self.element.find(".seat-file").hide();
            }

            self.updateTotalAmount();
        },

        _getCSRFToken: function() {
            var self = this;
            var crsfNode = self.element.find("[name='csrfmiddlewaretoken']");
            if( crsfNode.length > 0 ) {
                return crsfNode.val();
            }
            return getMetaCSRFToken();
        },

        /** Update total amount charged on card based on selected subscription
            charges. */
        updateTotalAmount: function() {
            var self = this;
            var candidates = self.element.find("input:radio");
            var totalAmountNode = self.element.find(".total-amount");
            var totalAmount = 0;
            for( var i = 0; i < candidates.length; ++i ) {
                var radio = $(candidates[i]);
                if( radio.is(":checked") ) {
                    totalAmount += parseInt(radio.attr('data-amount'));
                }
            }
            candidates = self.element.find(".invoice-item td:nth-child(2)");
            for( i = 0; i < candidates.length; ++i ) {
                var lineAmountText = $(candidates[i]).text().replace(',','');
                var first = lineAmountText.search("[0-9]");
                if( first > 0 ) {
                    var lineAmount = parseFloat(
                        lineAmountText.substring(first)) * 100;
                    totalAmount += lineAmount;
                }
            }
            var totalAmountText = "" + (totalAmount / 100).toFixed(2);
            if( self.options.currency_unit === "usd"
                || self.options.currency_unit === "cad" ) {
                totalAmountText = "$" + totalAmountText;
            } else if( self.options.currency_unit === "eur" ) {
                totalAmountText = "\u20ac" + totalAmountText;
            }
            var grouped = "";
            var sep = "";
            for( var idx = totalAmountText.length - 3 ; idx > 3; idx -= 3 ) {
                grouped += totalAmountText.substring(idx - 3, idx) + sep;
                sep = ",";
            }
            grouped = (totalAmountText.substring(0, idx) + grouped
                       + totalAmountText.substring(totalAmountText.length - 3));
            if( self.options.currency_unit === "cad" ) {
                grouped = grouped + " CAD";
            }
            totalAmountNode.text(grouped);
            var cardUse = self.element.parents("form").find("#card-use");
            if( totalAmount > 0 ) {
                if( !cardUse.is(":visible") ) { cardUse.slideDown(); }
            } else {
                if( cardUse.is(":visible") ) { cardUse.slideUp(); }
            }
        },

        updateUploadButtonVisibility: function(fileInput) {
            var button = fileInput.parents("td").find(".seat-upload-file");
            if (fileInput.get(0).files.length === 0) {
                button.hide();
            } else {
                button.show();
            }
        },

        createLineMessage: function(data) {
            return data.full_name + " (" + data.sync_on + ")";
        },

        insertLine: function(data) {
            var msg = this.createLineMessage(data);
            var prevLine = this.element.find("tbody[data-plan='" +
                data.plan + "'] .invoice-item").last();
            var newLine = prevLine.clone();
            var clonedNode = $(newLine.children("td")[2]);

            prevLine.removeClass("alert alert-info");
            var txt = clonedNode.text().split(', for');
            clonedNode.text(txt[0] + ", for " + msg);
            newLine.insertAfter(prevLine);
            newLine.addClass("alert alert-info");

            this.updateTotalAmount();
        },

        updateLine: function(data) {
            var msg = this.createLineMessage(data);
            var prevLine = this.element.find("tbody[data-plan='" +
                data.plan + "'] .invoice-item")
            var dup = null;
            prevLine.each(function(i){
                var $t = $(this);
                if($t.find('td:last-child').text().indexOf(data.sync_on) !== -1){
                    dup = $t;
                }
            });
            if(dup){
                prevLine = dup;
            } else {
                prevLine = prevLine.first();
            }
            var newLine = prevLine;
            var descrNode = $(newLine.children("td")[2]);

            var txt = descrNode.text().split(', for');
            descrNode.text(txt[0] + ", for " + msg);
            newLine.addClass("alert alert-info");

            this.updateTotalAmount();
        }
    };

    $.fn.invoice = function(options) {
        var opts = $.extend( {}, $.fn.invoice.defaults, options );
        return new Invoice($(this), opts);
    };

    $.fn.invoice.defaults = {
        currency_unit: "usd",
        saas_api_cart: "/api/cart/"
    };

   /** redeem a ``Coupon``.

        HTML requirements:

        <form>
            <input name="code">
            <input type="hidden" name="csrfmiddlewaretoken" value="...">
        </form>
    */
   function Redeem(el, options){
      this.element = $(el);
      this.options = options;
      this.init();
   }

   Redeem.prototype = {
      init: function () {
          var self = this;
          self.element.find(".submit-code").click(function() {
              var code = self.element.find("[name='code']").val();
              self.redeemCode(code);
              // prevent the form from submitting with the default action
              return false;
          });
      },

      _getCSRFToken: function() {
          var self = this;
          var crsfNode = self.element.find("[name='csrfmiddlewaretoken']");
          if( crsfNode.length > 0 ) {
              return crsfNode.val();
          }
          return getMetaCSRFToken();
      },

      redeemCode: function(code) {
          var self = this;
          $.ajax({ type: "POST",
                   url: self.options.saas_api_redeem_coupon,
                   beforeSend: function(xhr) {
                      xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                   },
                   data: JSON.stringify({"code": code}),
                   dataType: "json",
                   contentType: "application/json; charset=utf-8",
                   success: function(data) {
                     // XXX does not show messages since we reload...
                     showMessages([data.details], "success");
                     location.reload();
                   },
                   error: function(resp) {
                       showErrorMessages(resp);
                   }});
          return false;
      }
   };

   $.fn.redeem = function(options) {
      var opts = $.extend( {}, $.fn.redeem.defaults, options );
      return new Redeem($(this), opts);
   };

   $.fn.redeem.defaults = {
       saas_api_redeem_coupon: "/api/cart/redeem/"
   };


   /** Decorate an HTML controller to trigger AJAX requests to create,
       activate and delete ``Plan``s.

       HTML requirements:

       <div data-plan="_plan-slug_">
         <button class="activate"></button>
         <button class="delete"></button>
       </div>
    */
   function Plan(el, options){
      this.element = $(el);
      this.options = options;
      this.init();
   }

   Plan.prototype = {
      init: function () {
          var self = this;
          self.id = self.element.attr("data-plan");
          self.element.find(".activate").click(function() {
              self.toggleActivatePlan();
              // prevent the form from submitting with the default action
              return false;
          });
          var deleteBtn = self.element.find(".delete");
          if( deleteBtn ) {
              var target = deleteBtn.data("target");
              if( target !== undefined ) {
                  deleteBtn = $(target).find(".delete");
              }
          }
          deleteBtn.click(function() {
              self.destroy();
          });
      },

      _getCSRFToken: function() {
          var self = this;
          var crsfNode = self.element.find("[name='csrfmiddlewaretoken']");
          if( crsfNode.length > 0 ) {
              return crsfNode.val();
          }
          return getMetaCSRFToken();
      },

      create: function(reload) {
        "use strict";
        var self = this;
        $.ajax({ type: "POST",
                 url: self.options.saas_api_plan + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                 },
                 data: JSON.stringify({
                     "title": gettext("New Plan"),
                     "description": gettext("Write the description of the plan here."),
                     "interval": 4,
                     "is_active": 1}),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     showMessages([
                         gettext("Plan was created successfully.")], "success");
                     if( reload ) { location.reload(true); }
                 },
                 error: function(resp) {
                     showErrorMessages(resp);
                 }
               });
      },

      /** Update fields in a ``Plan`` by executing an AJAX request
          to the service. */
      update: function(data, successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "PUT",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                 },
                 async: false,
                 data: JSON.stringify(data),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunction
               });
      },

      destroy: function() {
        "use strict";
        var self = this;
        $.ajax({ type: "DELETE",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                 },
                 async: false,
                 success: function(data) {
                     window.location.href = self.options.saas_metrics_plans;
                     showMessages([
                         gettext("Plan was successfully deleted.")], "success");
                 },
                 error: function(resp) {
                     showErrorMessages(resp);
                 }
               });
      },

      get: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "GET",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 success: successFunction
               });
      },

      /** Toggle a ``Plan`` from active to inactive and vise-versa
          by executing an AJAX request to the service. */
      toggleActivatePlan: function() {
          "use strict";
          var self = this;
          var button = self.element.find(".activate");
          $.ajax({type: "PUT",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", self._getCSRFToken());
                 },
                 data: JSON.stringify({
                     "is_active": !button.hasClass("activated")}),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     if( data.is_active ) {
                         button.addClass("activated");
                         button.text("Deactivate");
                     } else {
                         button.removeClass("activated");
                         button.text("Activate");
                     }
                 },
                 error: function(resp) {
                     showErrorMessages(resp);
                 },
          });
      }
   };

   $.fn.plan = function(options) {
      var opts = $.extend( {}, $.fn.plan.defaults, options );
      return new Plan($(this), opts);
   };

   $.fn.plan.defaults = {
       saas_api_plan: "/api/plan",
       saas_metrics_plans: "/plan"
   };

})(jQuery);
