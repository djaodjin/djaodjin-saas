/*=============================================================================
  Filters
  ============================================================================*/
angular.module('revenueFilters', [])
    .filter('monthHeading', function() {
        var current = moment();
        return function(datestr) {
            var date = moment(datestr);
            var heading = date.format('MMM\'YY');
            if( date > current ) {
                // add incomplete month marker
                heading += '*';
            }
            return heading;
        };
    })
    .filter('humanizeCell', function(currencyFilter, numberFilter) {
        return function(cell, unit, scale) {
            scale = scale || 1;
            var value = cell * scale;
            if(unit) {
                if(parseInt(value) > 1000){
                    return currencyFilter((parseInt(value) / 1000).toFixed(), unit, 0) + "K";
                }
                return currencyFilter(value, unit);
            }
            return numberFilter(value);
        }
    });


/*=============================================================================
  Apps
  ============================================================================*/

angular.module('couponApp', ['ui.bootstrap', 'ngRoute',
    'couponControllers', 'couponServices']);
angular.module('userRelationApp', ['ui.bootstrap', 'ngRoute',
    'userRelationControllers', 'userRelationServices']);
angular.module('subscriptionApp', ['ui.bootstrap', 'ngRoute',
    'subscriptionControllers', 'subscriptionServices']);
angular.module('subscriberApp', ['ui.bootstrap', 'ngRoute',
    'subscriberControllers']);
angular.module('transactionApp', ['ui.bootstrap', 'ngRoute',
    'transactionControllers', 'transactionServices']);
angular.module('metricApp', ['ui.bootstrap', 'ngRoute', 'metricControllers']);
angular.module('metricsApp', ['ui.bootstrap', 'ngRoute', 'metricsControllers', 'revenueFilters']);


/*=============================================================================
  Services
  ============================================================================*/

var couponServices = angular.module('couponServices', ['ngResource']);
var userRelationServices = angular.module('userRelationServices', ['ngResource']);
var subscriptionServices = angular.module('subscriptionServices', [
    'ngResource']);
var transactionServices = angular.module('transactionServices', ['ngResource']);


couponServices.factory('Coupon', ['$resource', 'urls',
  function($resource, urls){
    "use strict";
    return $resource(
        urls.saas_api_coupon_url + '/:coupon', {'coupon':'@code'},
            {query: {method:'GET'},
             create: {method:'POST'},
             update: {method:'PUT', isArray:false}});
  }]);

userRelationServices.factory('UserRelation', ['$resource', 'urls',
  function($resource, urls){
    "use strict";
    return $resource(
        urls.saas_api_user_relation_url + '/:user', {'user':'@user'},
        {force: {method:'POST', params: {force:true}}});
  }]);

subscriptionServices.factory('Subscription', ['$resource', 'urls',
  function($resource, urls){
    "use strict";
    return $resource(
        urls.saas_api_subscription_url + '/:plan', {plan:'@plan'},
            {query: {method:'GET'}});
  }]);

transactionServices.factory('Transaction', ['$resource', 'urls',
  function($resource, urls){
    "use strict";
    return $resource(
        urls.saas_api_transaction_url + '/:id', {id:'@id'},
            {query: {method:'GET'}});
  }]);

/*=============================================================================
  Controllers
  ============================================================================*/

var couponControllers = angular.module('couponControllers', []);
var userRelationControllers = angular.module('userRelationControllers', []);
var subscriptionControllers = angular.module('subscriptionControllers', []);
var subscriberControllers = angular.module('subscriberControllers', []);
var transactionControllers = angular.module('transactionControllers', []);
var metricControllers = angular.module('metricControllers', []);
var metricsControllers = angular.module('metricsControllers', []);

couponControllers.controller('CouponListCtrl',
    ['$scope', '$http', '$timeout', 'Coupon', 'urls',
     function($scope, $http, $timeout, Coupon, urls) {
    "use strict";
    $scope.urls = urls;
    $scope.totalItems = 0;
    $scope.dir = {code: 'asc'};
    $scope.params = {o: 'code', ot: $scope.dir.code};
    $scope.coupons = Coupon.query($scope.params, function() {
        /* We cannot watch coupons.count otherwise things start
           to snowball. We must update totalItems only when it truly changed.*/
        if( $scope.coupons.count != $scope.totalItems ) {
            $scope.totalItems = $scope.coupons.count;
        }
    });
    $scope.newCoupon = new Coupon();

    $scope.filterExpr = '';
    $scope.itemsPerPage = 25; // Must match on the server-side.
    $scope.maxSize = 5;      // Total number of pages to display
    $scope.currentPage = 1;

    $scope.dateOptions = {
        formatYear: 'yy',
        startingDay: 1
    };

    $scope.initDate = new Date('2016-15-20');
    $scope.minDate = new Date();
    $scope.maxDate = new Date('2016-01-01');
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    $scope.filterList = function(regex) {
        if( regex ) {
            $scope.params.q = regex;
        } else {
            delete $scope.params.q;
        }
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count != $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    };

    // calendar for expiration date
    $scope.open = function($event, coupon) {
        $event.preventDefault();
        $event.stopPropagation();
        coupon.opened = true;
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count != $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    };

    $scope.remove = function (idx) {
        Coupon.remove({ coupon: $scope.coupons.results[idx].code },
        function (success) {
            $scope.coupons = Coupon.query($scope.params, function() {
                if( $scope.coupons.count != $scope.totalItems ) {
                    $scope.totalItems = $scope.coupons.count;
                }
            });
        });
    };

    $scope.save = function() {
        $http.post(urls.saas_api_coupon_url, $scope.newCoupon).success(
        function(result) {
            $scope.coupons.results.push(new Coupon(result));
            // Reset our editor to a new blank post
            $scope.newCoupon = new Coupon();
        });
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] == 'asc' ) {
            $scope.dir = {};
            $scope.dir[fieldName] = 'desc';
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = 'asc';
        }
        $scope.params.o = fieldName;
        $scope.params.ot = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params.page;
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count != $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    };

    $scope.$watch('coupons', function(newVal, oldVal, scope) {
        if( newVal.hasOwnProperty('results') &&
            oldVal.hasOwnProperty('results') ) {
            var length = ( oldVal.results.length < newVal.results.length ) ?
                oldVal.results.length : newVal.results.length;
            for( var i = 0; i < length; ++i ) {
                if( (oldVal.results[i].ends_at != newVal.results[i].ends_at) || (oldVal.results[i].description != newVal.results[i].description)) {
                    Coupon.update(newVal.results[i], function(result) {
                        // XXX We don't show messages here because it becomes
                        // quickly annoying if they do not disappear
                        // automatically.
                        // showMessages(["Coupon was successfully updated."], 'success');
                    });
                }
            }
        }
    }, true);

    $scope.editDescription = function (idx){
        $scope.edit_description = Array.apply(
            null, new Array($scope.coupons.results.length)).map(function() {
            return false;
        });
        $scope.edit_description[idx] = true;
        $timeout(function(){
            angular.element('#input_description').focus();
        }, 100);
    };

    $scope.saveDescription = function(event, coupon, idx){
        if (event.which === 13 || event.type == 'blur' ){
            $scope.edit_description[idx] = false;
        }
    };
}]);


userRelationControllers.controller('userRelationListCtrl',
    ['$scope', '$http', 'UserRelation', 'urls',
    function($scope, $http, UserRelation, urls) {
    "use strict";
    $scope.users = UserRelation.query();
    $scope.user = null;

    $scope.create = function() {
        $scope.user.invite = $("#new-user-relation [name='message']").val();
        (new UserRelation($scope.user)).$force(
            function(success) {
                /* XXX Couldn't figure out how to get the status code
                   here so we just reload the list. */
                $scope.users = UserRelation.query();
                $scope.user = null;
            },
            function(error) {
                var errMsg = error.statusText;
                if( error.data && error.data.detail ) {
                    errMsg = error.data.detail;
                }
                showMessages([errMsg], 'danger');
            });
    };

    $scope.save = function() {
        (new UserRelation($scope.user)).$save(
            function(success) {
                /* XXX Couldn't figure out how to get the status code
                   here so we just reload the list. */
                $scope.users = UserRelation.query();
                $scope.user = null;
            },
            function(error) {
                if( error.status == 404 ) {
                    $scope.user.email = $scope.user.username;
                    $("#new-user-relation").modal('show');
                } else {
                    var errMsg = error.statusText;
                    if( error.data && error.data.detail ) {
                        errMsg = error.data.detail;
                    }
                    showMessages([errMsg], 'danger');
                }
            });
    };

    $scope.getUsers = function(val) {
        return $http.get(urls.saas_api_user_url, {
            params: {q: val}
        }).then(function(res){
            return res.data;
        });
    };

    $scope.remove = function (idx) {
        UserRelation.remove({ user: $scope.users[idx].username },
        function (success) {
            $scope.users.splice(idx, 1);
        });
    };
}]);


subscriptionControllers.controller('subscriptionListCtrl',
    ['$scope', '$http', '$timeout', 'Subscription', 'urls',
    function($scope, $http, $timeout, Subscription, urls) {
    "use strict";
    var defaultSortByField = 'created_at';
    $scope.dir = {};
    $scope.totalItems = 0;
    $scope.dir[defaultSortByField] = 'desc';
    $scope.params = {o: defaultSortByField, ot: $scope.dir[defaultSortByField]};
    $scope.subscriptions = Subscription.query($scope.params, function() {
        /* We cannot watch subscriptions.count otherwise things start
           to snowball. We must update totalItems only when it truly changed.*/
        if( $scope.subscriptions.count != $scope.totalItems ) {
            $scope.totalItems = $scope.subscriptions.count;
        }
    });

    $scope.filterExpr = '';
    $scope.itemsPerPage = 25; // Must match on the server-side.
    $scope.maxSize = 5;      // Total number of pages to display
    $scope.currentPage = 1;

    $scope.dateOptions = {
        formatYear: 'yy',
        startingDay: 1
    };

    $scope.initDate = new Date('2016-15-20');
    $scope.minDate = new Date();
    $scope.maxDate = new Date('2016-01-01');
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    $scope.editDescription = function (event, entry) {
        var input = angular.element(event.target).parent().find('input');
        entry.editDescription = true;
        $timeout(function() {
            input.focus();
        }, 100);
    };

    $scope.saveDescription = function(event, entry){
        if (event.which === 13 || event.type == 'blur' ){
            delete entry.editDescription;
            $http.patch(urls.saas_api + entry.organization.slug +
                "/subscriptions/" + entry.plan.slug,
                {description: entry.description}).then(
                function(data){
                    // XXX message expiration date was updated.
            });
        }
    };

    $scope.filterList = function(regex) {
        if( regex ) {
            $scope.params.q = regex;
        } else {
            delete $scope.params.q;
        }
        $scope.subscriptions = Subscription.query($scope.params, function() {
            if( $scope.subscriptions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.subscriptions.count;
            }
        });
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
        $scope.subscriptions = Subscription.query($scope.params, function () {
            if( $scope.subscriptions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.subscriptions.count;
            }
        });
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] == 'asc' ) {
            $scope.dir = {};
            $scope.dir[fieldName] = 'desc';
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = 'asc';
        }
        $scope.params.o = fieldName;
        $scope.params.ot = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.paramspage;
        $scope.subscriptions = Subscription.query($scope.params, function () {
            if( $scope.subscriptions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.subscriptions.count;
            }
        });
    };

    $scope.unsubscribe = function(organization, plan) {
        if( confirm("Are you sure?") ) {
            $http.delete(
                urls.saas_api + organization + "/subscriptions/" + plan).then(
            function() {
                $scope.subscriptions = Subscription.query($scope.params,
            function() {
                if( $scope.subscriptions.count != $scope.totalItems ) {
                    $scope.totalItems = $scope.subscriptions.count;
                }
            });
            });
        }
    };
}]);


subscriberControllers.controller('subscriberCtrl',
    ['$scope', '$http', 'urls',
    function($scope, $http, urls) {
    "use strict";
    $scope.opened = { 'start_at': false, 'ends_at': false };
    $scope.start_at = new Date();
    $scope.ends_at = new Date();
    $scope.registered_loading = false;
    $scope.subscribed_loading = false;
    $scope.churned_loading = false;

    $scope.minDate = new Date('2014-01-01');
    $scope.maxDate = new Date('2016-01-01');
    $scope.dateOptions = {formatYear: 'yy', startingDay: 1};
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    // initialized with *maxSize* empty items for layout during first load.
    $scope.registered = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    $scope.subscribed = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    $scope.churned = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];

    $scope.maxSize = 5;  // Total number of pages to display
    $scope.itemsPerPage = 25; // Must match on the server-side.
    $scope.currentPage = {churned: 1, registered: 1, subscribed: 1};

    // calendar for start_at and ends_at
    $scope.open = function($event, date_at) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened[date_at] = true;
    };

    // XXX start_at and ends_at will be both updated on reload
    //     which will lead to two calls to the backend instead of one.
    $scope.$watch('start_at', function(newVal, oldVal, scope) {
        if( $scope.ends_at < newVal ) {
            $scope.ends_at = newVal;
        }
        $scope.refresh();
    }, true);

    $scope.$watch('ends_at', function(newVal, oldVal, scope) {
        if( $scope.start_at > newVal ) {
            $scope.start_at = newVal;
        }
        $scope.refresh();
    }, true);

    $scope.pageChanged = function(dataset) {
        $scope.refresh(dataset);
    };

    $scope.refresh = function(dataset) {
        $scope.registered_loading = true;
        $scope.subscribed_loading = true;
        $scope.churned_loading = true;
        if( typeof dataset === "undefined" || dataset == 'churned' ) {
            var params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.churned > 1 ) {
                params.page = $scope.currentPage.churned;
            }
            $http.get(urls.saas_api_churned, {
                params: params
            }).success(function(data) {
                $scope.churned_loading = false;
                $scope.churned = data;
                for( var i = $scope.churned.churned.length;
                     i < $scope.itemsPerPage; ++i ) {
                    $scope.churned.churned.push({});
                }
            });
        }
        if( typeof dataset === "undefined" || dataset == 'registered' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.registered > 1 ) {
                params.page = $scope.currentPage.registered;
            }
            $http.get(urls.saas_api_registered, {
                params: params
            }).success(function(data) {
                $scope.registered_loading = false;
                $scope.registered = data;
                for( var i = $scope.registered.registered.length;
                     i < $scope.itemsPerPage; ++i ) {
                    $scope.registered.registered.push({});
                }
            });
        }
        if( typeof dataset === "undefined" || dataset == 'subscribed' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.subscribed > 1 ) {
                params.page = $scope.currentPage.subscribed;
            }
            $http.get(urls.saas_api_subscribed, {
                params: params
            }).success(function(data) {
                $scope.subscribed_loading = false;
                $scope.subscribed = data;
                for( var i = $scope.subscribed.subscribed.length;
                     i < $scope.itemsPerPage; ++i ) {
                    $scope.subscribed.subscribed.push({});
                }
            });
        }
    };

    $scope.endsSoon = function(organization) {
        var cutOff = new Date($scope.ends_at);
        cutOff.setDate($scope.ends_at.getDate() + 5);
        for( var i = 0; i < organization.subscriptions.length; ++i ) {
            var sub = organization.subscriptions[i];
            var subEndsAt = new Date(sub.ends_at);
            if( subEndsAt < cutOff ) {
                return "ends-soon";
            }
        }
        return "";
    };

    $scope.relativeDate = function(organization, future) {
        var cutOff = new Date($scope.ends_at);
        var dateTime = new Date(organization.created_at);
        for( var i = 0; i < organization.subscriptions.length; ++i ) {
            var sub = organization.subscriptions[i];
            var subEndsAt = new Date(sub.ends_at);
            if( future ) {
                if( dateTime < cutOff ||
                    (subEndsAt > cutOff && subEndsAt < dateTime) ) {
                    dateTime = subEndsAt;
                }
            }
        }
        if( dateTime <= cutOff ) {
            return moment.duration(cutOff - dateTime).humanize() + ' ago';
        } else {
            return 'for ' + moment.duration(dateTime - cutOff).humanize();
        }
    };

}]);


transactionControllers.controller('transactionListCtrl',
    ['$scope', '$http', '$timeout', 'Transaction',
     function($scope, $http, $timeout, Transaction) {
    "use strict";
    var defaultSortByField = 'date';
    $scope.dir = {};
    $scope.totalItems = 0;
    $scope.dir[defaultSortByField] = 'desc';
    $scope.opened = { 'start_at': false, 'ends_at': false };
    $scope.start_at = moment().subtract(1, 'months').startOf('day').toDate();
    $scope.ends_at = moment().endOf('day').toDate();
    $scope.params = {
        o: defaultSortByField,
        ot: $scope.dir[defaultSortByField],
        start_at: $scope.start_at,
        ends_at: $scope.ends_at
    };

    $scope.refresh = function() {
        $scope.transactions = Transaction.query($scope.params, function() {
            /* We cannot watch transactions.count otherwise things start
               to snowball. We must update totalItems only when it truly changed.*/
            if( $scope.transactions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.transactions.count;
            }
        });
    };
    $scope.refresh();

    $scope.filterExpr = '';
    $scope.itemsPerPage = 25; // Must match on the server-side.
    $scope.maxSize = 5;      // Total number of pages to display
    $scope.currentPage = 1;
    /* currentPage will be saturated at maxSize when maxSize is defined. */

    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    // calendar for start_at and ends_at
    $scope.open = function($event, date_at) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened[date_at] = true;
    };

    // XXX start_at and ends_at will be both updated on reload
    //     which will lead to two calls to the backend instead of one.
    $scope.$watch('start_at', function(newVal, oldVal, scope) {
        if( $scope.ends_at < newVal ) {
            $scope.ends_at = newVal;
        }
        $scope.params.start_at = moment(newVal).startOf('day').toDate();
        $scope.refresh();
    }, true);

    $scope.$watch('ends_at', function(newVal, oldVal, scope) {
        if( $scope.start_at > newVal ) {
            $scope.start_at = newVal;
        }
        $scope.params.ends_at = moment(newVal).endOf('day').toDate(0);
        $scope.refresh();
    }, true);


    $scope.filterList = function(regex) {
        if( regex ) {
            $scope.params.q = regex;
        } else {
            delete $scope.params.q;
        }
        $scope.transactions = Transaction.query($scope.params, function() {
            if( $scope.transactions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.transactions.count;
            }
        });
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
        $scope.transactions = Transaction.query($scope.params, function() {
            if( $scope.transactions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.transactions.count;
            }
        });
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] == 'asc' ) {
            $scope.dir = {};
            $scope.dir[fieldName] = 'desc';
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = 'asc';
        }
        $scope.params.o = fieldName;
        $scope.params.ot = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params.page;
        $scope.transactions = Transaction.query($scope.params, function() {
            if( $scope.transactions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.transactions.count;
            }
        });
    };

}]);


metricControllers.controller('metricCtrl',
    ['$scope', '$http', 'urls',
     function($scope, $http, urls) {
    "use strict";
    $scope.balances = [];
    $http.get(urls.saas_api_metrics_balance).success(
        function(data) {
            $scope.balances = data;
    });
}]);

metricsControllers.controller('metricsCtrl',
    ['$scope', '$http', 'urls', 'tables',
    function($scope, $http, urls, tables) {

    $scope.tables = tables;

    $scope.tabs = [];
    for( var i = 0; i < $scope.tables.length; ++i ) {
        $scope.tabs.push($scope.tables[i].key);
    }
    $scope.activeTab = $scope.tabs[0];

    $scope.endOfMonth = function(date) {
        return new Date(
            date.getFullYear(),
            date.getMonth() + 1,
            0
        )
    };
    $scope.ends_at = new Date();

    // these aren't documented; do they do anything?
    $scope.formats = ["MM-yyyy", "yyyy/MM", "MM.yyyy"];
    $scope.format = $scope.formats[0];
    $scope.dateOptions = {
        formatYear: "yyyy",
        startingDay: 1,
        mode: "month",
        minMode: "month"
    };
    $scope.opened = false;

    $scope.getTable = function(key) {
        for( var i = 0; i < $scope.tables.length; ++i ) {
            if( $scope.tables[i].key === key ) {
                return $scope.tables[i];
            }
        }
        return null;
    }

    $scope.refreshTable = function() {
        $http.get(
            $scope.getTable($scope.activeTab).location,
            {params: {"ends_at": $scope.ends_at}}
        ).success(
            function(data) {
                var unit = data.unit;
                var scale = data.scale;
                scale = parseFloat(scale);
                if( isNaN(scale) ) {
                    scale = 1.0;
                }
                // add "extra" rows at the end
                var extra = data.extra || [];

                var table = $scope.getTable($scope.activeTab);
                table.unit = unit;
                table.scale = scale;
                table.data = data.table;

                // manual binding - trigger updates to the graph
                if( table.key == "balances") {
                    // XXX Hard-coded.
                    updateBarChart("#metrics-table svg",
                        data.table, unit, scale, extra);
                } else {
                    updateChart("#metrics-table svg",
                        data.table, unit, scale, extra);
                }
            }
        );
    };
    $scope.refreshTable();

    // change the selected tab
    $scope.tabClicked = function($event) {
        $scope.activeTab = $event.target.getAttribute("href").replace(/^#/, "");
        $scope.refreshTable();
    };

    // open the date picker
    $scope.open = function($event) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened = true;
    };

    $scope.$watch("ends_at", function(newVal, oldVal, scope) {
        if (newVal !== oldVal) {
            $scope.ends_at = $scope.endOfMonth(newVal);
            $scope.refreshTable();
        }
    }, true);
}]);
