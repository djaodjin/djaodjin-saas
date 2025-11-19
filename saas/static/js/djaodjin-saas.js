/**
   Functionality related to the cart and checkout of djaodjin-saas.

   These are based on jquery.
 */

/*global location setTimeout jQuery*/
/*global djApi showMessages showErrorMessages */


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
        this.el = el;
        this.$el = $(el);
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
            if( self.$el.attr('id') ) {
                self.item.plan = self.$el.attr('id');
            }
            self.submitBtn = self.$el.find("[type='submit']");
            if( self.submitBtn.empty() ) {
                self.submitBtn = self.$el;
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

        add: function() {
            var self = this;
            djApi.post(self.el, self.options.api_cart, self.item,
            function(data) {
                if( self.options.reload ) {
                    location.reload();
                } else {
                    self.submitBtn.text(self.options.removeLabel);
                }
            });
        },

        remove: function(successFunction) {
            var self = this;
            djApi.delete(self.el,
                self.options.api_cart + "?plan=" + self.item.plan,
            function(data) {
                if( self.options.reload ) {
                    location.reload();
                } else {
                    self.submitBtn.text(self.options.addLabel);
                }
            });
        }
    };

    $.fn.cartItem = function(options) {
        var opts = $.extend( {}, $.fn.cartItem.defaults, options );
        return this.each(function() {
            if (!$.data(this, "cartItem")) {
                $.data(this, "cartItem", new CartItem(this, opts));
            }
        });
    };

    $.fn.cartItem.defaults = {
        api_cart: '/api/cart/',
        addLabel: "Add to Cart",
        removeLabel: "Remove from Cart",
        nb_periods: 1,
        reload: false
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
        this.el = el;
        this.$el = $(el);
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
            djApi.get(self.el, self.options.saas_api_charge,
            function(data) {
                if( data.state === "created" ) {
                    setTimeout(function() {
                        self.waitForCompletion(); }, 1000);
                } else {
                    var statusElement = self.$el.find(".charge-status");
                    statusElement.text(
                        statusElement.attr("data-charge-" + data.state));
                }
            });
        }
    };

    $.fn.chargeMonitor = function(options) {
        var opts = $.extend( {}, $.fn.chargeMonitor.defaults, options );
        return this.each(function() {
            if (!$.data(this, "chargeMonitor")) {
                $.data(this, "chargeMonitor", new ChargeMonitor(this, opts));
            }
        });
    };

    $.fn.chargeMonitor.defaults = {
        saas_api_charge: null,
        initialState: "created",
    };

    /** Email a receipt for a charge. This behavior is typically associated
        to a button.
     */
    function ChargeEmailReceipt(el, options){
        this.el = el;
        this.$el = $(el);
        this.options = options;
        this.init();
    }

    ChargeEmailReceipt.prototype = {
        init: function () {
            var self = this;
            self.state = self.options.initialState;
            self.$el.submit(function (event) {
                event.preventDefault();
                self.emailReceipt();
            });
        },

        emailReceipt: function() {
            var self = this;
            if( self.state === "created" ) {
                setTimeout(function() {
                    djApi.get(self.el, self.options.saas_api_charge,
                    function(data) {
                        self.state = data.state;
                        self.emailReceipt();
                    });
                }, 1000);
            } else {
                djApi.post(self.el, self.options.saas_api_email_charge_receipt,
                function(data) {
                    if( data.detail ) {
                        showMessages([data.detail], "info");
                    }
                });
            }
            return 0;
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
        self.el = el;
        self.$el = $(el);
        self.setOptions(options);
        self.init();
    }

    Refund.prototype = {
        init: function () {
            var self = this;
            // Make sure we unbind the previous handler to avoid double submits
            self.$el.off("submit.refund");
            self.$el.on("submit.refund", function() {
                if( typeof self.$el.modal !== 'undefined' ) {
                    self.$el.modal("hide");
                }
                self.submit();
                // prevent the form from submitting with the default action
                return false;
            });
        },

        setOptions: function(opts) {
            var self = this;
            self.options = opts;
            var refundedInput = self.$el.find("[name='amount']");
            var availableAmount =
                (self.options.availableAmount / 100).toFixed(2);
            refundedInput.attr("max", availableAmount);
            refundedInput.attr("data-linenum", self.options.linenum);
            refundedInput.val(availableAmount);
        },

        submit: function() {
            var self = this;
            var refundButton = self.options.refundButton;
            var refundedInput = self.$el.find("[name='amount']");
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
                djApi.post(self.el,
                    self.options.saas_api_charge_refund, {"lines":[{
                    "num": linenum, "refunded_amount": refundedAmount}]},
                function(data) {
                    var message = data.detail ?
                        data.detail : "Amount refunded.";
                    if( message ) {
                        showMessages([message], "info");
                    }
                    refundButton.replaceWith(self.options.refundedLabel);
                },
                function(resp) {
                    showErrorMessages(resp);
                    refundButton.removeAttr("disabled");
                });
            }
            return false;
        }
    };

    $.fn.refund = function(options) {
        var opts = $.extend({}, $.fn.refund.defaults, options);
        return this.each(function() {
            var element = this;
            var refund = $.data(element, "refund");
            if( !refund ) {
                var v = $.data(element, "refund", new Refund(element, opts));
            } else {
                refund.setOptions(opts);
            }
        });
    };

    $.fn.refund.defaults = {
        saas_api_charge_refund: null,
        availableAmount: 0,
        linenum: 0,
        refundButton: null,
        refundedLabel: "<em>Refunded</em>"
    };

    /** Invoice
     */
    function Invoice(el, options){
        this.el = el;
        this.$el = $(el);
        this.options = options;
        this.init();
    }

    Invoice.prototype = {
        init: function () {
            var self = this;

            self.$el.find("input:radio").change(function() {
                self.updateTotalAmount();
            });

            self.$el.find(".remove-from-cart").click(function(event) {
                event.preventDefault();
                var plan = $(this).attr('id');
                djApi.delete(self.el,
                    self.options.saas_api_cart + "?plan=" + plan,
                    function(data) {
                        location.reload();
                });
                return false;
            });

            self.$el.find(".add-seat").click(function(event) {
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
                djApi.post(self.el, self.options.saas_api_cart, item,
                function(data, textStatus, jqXHR) {
                    if( jqXHR.status === 201 ) {
                        self.insertLine(data);
                    } else {
                        self.updateLine(data);
                    }
                });
                return false;
            });

            self.$el.find(".seat-upload-file").click(function(event) {
                var file = $(this).parents("td").find(".seat-file");
                var plan = $(this).parents("tbody").attr("data-plan");
                if (file.get(0).files.length > 0) {
                    var formData = new FormData();
                    formData.append("file", file.get(0).files[0]);
                    djApi.postBlob(self.el,
                        self.options.saas_api_cart + "/" + plan + "/upload",
                        formData,
                    function(data) {
                        for (var i in data.created) {
                            self.insertLine(data.created[i]);
                        }
                        for (var i in data.updated) {
                            self.updateLine(data.updated[i]);
                        }
                        file.val("").change();
                    });
                }
            });

            self.$el.find(".seat-file").change(function(event) {
                self.updateUploadButtonVisibility($(this));
            }).each(function() {
                self.updateUploadButtonVisibility($(this));
            });

            if(window.FormData === undefined) {
                self.$el.find(".seat-file").hide();
            }

            self.updateTotalAmount();
        },

        /** Update total amount charged on card based on selected subscription
            charges. */
        updateTotalAmount: function() {
            var self = this;
            var candidates = self.$el.find("input:radio");
            var totalAmountNode = self.$el.find(".total-amount");
            var totalAmount = 0;
            for( var i = 0; i < candidates.length; ++i ) {
                var radio = $(candidates[i]);
                if( radio.is(":checked") ) {
                    totalAmount += parseInt(radio.attr('data-amount'));
                }
            }
            candidates = self.$el.find(".invoice-item .line-amount");
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
            var cardUse = self.$el.parents("form").find("#card-use");
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

        insertLine: function(data) {
            var msg = data.detail;
            var planSlug = data.plan.slug;
            var prevLine = this.$el.find(
                "tbody[data-plan='" + planSlug + "'] .invoice-item").last();
            var newLine = prevLine.clone();
            var clonedNode = newLine.children("td.line-descr");

            prevLine.removeClass("alert alert-info");
            clonedNode.text(msg);
            newLine.insertAfter(prevLine);
            newLine.addClass("alert alert-info");

            this.updateTotalAmount();
        },

        updateLine: function(data) {
            var msg =  data.detail;
            var planSlug = data.plan.slug;
            var prevLine = this.$el.find(
                "tbody[data-plan='" + planSlug + "'] .invoice-item");
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
            var descrNode = newLine.children("td.line-descr");
            descrNode.text(msg);
            newLine.addClass("alert alert-info");

            this.updateTotalAmount();
        }
    };

    $.fn.invoice = function(options) {
        var opts = $.extend({}, $.fn.invoice.defaults, options);
        return this.each(function() {
            if (!$.data(this, "Invoice")) {
                $.data(this, "Invoice", new Invoice(this, opts));
            }
        });
    };

    $.fn.invoice.defaults = {
        saas_api_cart: "/api/cart",
        currency_unit: "usd",
    };

   /** redeem a ``Coupon``.

        HTML requirements:

        <form>
            <input name="code">
            <input type="hidden" name="csrfmiddlewaretoken" value="...">
        </form>
    */
   function Redeem(el, options){
       this.el = el;
       this.$el = $(el);
       this.options = options;
       this.init();
   }

   Redeem.prototype = {
      init: function () {
          var self = this;
          self.$el.find(".submit-code").click(function(event) {
              event.preventDefault();
              var code = self.$el.find("[name='code']").val();
              self.redeemCode(code);
              // prevent the form from submitting with the default action
              return false;
          });
      },

      redeemCode: function(code) {
          var self = this;
          console.log("XXX [redeemCode] self.el=", self.el);
          djApi.post(self.el, self.options.saas_api_redeem_coupon, {
              "code": code},
          function(data) {
              // XXX does not show messages since we reload...
              showMessages([data.detail], "success");
              location.reload();
          });
          return false;
      }
   };

   $.fn.redeem = function(options) {
       var opts = $.extend( {}, $.fn.redeem.defaults, options );
       return this.each(function() {
           if (!$.data(this, "Redeem")) {
               $.data(this, "Redeem", new Redeem(this, opts));
           }
       });
   };

   $.fn.redeem.defaults = {
       saas_api_redeem_coupon: "/api/cart/redeem/",
   };


   /** Decorate an HTML controller to trigger HTTP requests to create,
       activate and delete ``Plan``s.

       HTML requirements:

       <div data-plan="_plan-slug_">
         <button class="activate"></button>
         <button class="delete"></button>
       </div>
    */
   function Plan(el, options){
       this.el = el;
       this.$el = $(el);
       this.options = options;
       this.init();
   }

   Plan.prototype = {
      init: function () {
          var self = this;
          self.id = self.$el.attr("data-plan");
          self.$el.find(".activate").click(function() {
              self.toggleActivatePlan();
              // prevent the form from submitting with the default action
              return false;
          });
          var deleteBtn = self.$el.find(".delete");
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

      create: function(reload) {
        "use strict";
        var self = this;
        djApi.post(self.el,
            self.options.saas_api_plan, self.options.template_new,
        function(data) {
            showMessages([self.options.message_created], "success");
            if( reload ) { location.reload(true); }
        });
      },

      /** Update fields in a ``Plan`` by executing an HTTP request
          to the service. */
      update: function(data, successFunction) {
        "use strict";
        var self = this;
        djApi.put(self.el, self.options.saas_api_plan + "/" + self.id, data,
            successFunction
        );
      },

      destroy: function() {
        "use strict";
        var self = this;
        djApi.delete(self.el, self.options.saas_api_plan + "/" + self.id,
        function(data) {
            window.location.href = self.options.saas_metrics_plans;
            showMessages([self.options.message_deleted], "success");
        });
      },

      get: function(successFunction) {
        "use strict";
        var self = this;
        djApi.get(self.el, self.options.saas_api_plan + "/" + self.id,
            successFunction
        );
      },

      /** Toggle a ``Plan`` from active to inactive and vise-versa
          by executing an HTTP request to the service. */
      toggleActivatePlan: function() {
          "use strict";
          var self = this;
          var button = self.$el.find(".activate");
          djApi.put(self.el, self.options.saas_api_plan + "/" + self.id, {
              "is_active": !button.hasClass("activated")},
          function(data) {
              if( data.is_active ) {
                  button.addClass("activated");
                  button.text("Deactivate");
              } else {
                  button.removeClass("activated");
                  button.text("Activate");
              }
          });
      }
   };

   $.fn.plan = function(options) {
       var opts = $.extend({}, $.fn.plan.defaults, options);
       return this.each(function() {
           if (!$.data(this, "Plan")) {
               $.data(this, "Plan", new Plan(this, opts));
           }
       });
   };

   $.fn.plan.defaults = {
       saas_api_plan: "/api/plan",
       saas_metrics_plans: "/plan",
       message_created: "Plan was created successfully.",
       message_deleted: "Plan was successfully deleted.",
       template_new: {
           title: "New Plan",
           description: "Write the description of the plan here.",
           period_type: "monthly",
           is_active: 1
       }
   };

})(jQuery);
