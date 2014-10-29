/*=============================================================================
  Apps
  ============================================================================*/

angular.module('couponApp', ['ui.bootstrap', 'ngRoute',
    'couponControllers', 'couponServices']);
angular.module('contributorApp', ['ui.bootstrap', 'ngRoute',
    'contributorControllers', 'contributorServices']);
angular.module('managerApp', ['ui.bootstrap', 'ngRoute',
    'managerControllers', 'managerServices']);
angular.module('subscriptionApp', ['ui.bootstrap', 'ngRoute',
    'subscriptionControllers', 'subscriptionServices']);
angular.module('subscriberApp', ['ui.bootstrap', 'ngRoute',
    'subscriberControllers']);
angular.module('transactionApp', ['ui.bootstrap', 'ngRoute',
    'transactionControllers', 'transactionServices']);


/*=============================================================================
  Services
  ============================================================================*/

var couponServices = angular.module('couponServices', ['ngResource']);
var contributorServices = angular.module('contributorServices', ['ngResource']);
var managerServices = angular.module('managerServices', ['ngResource']);
var subscriptionServices = angular.module('subscriptionServices', [
    'ngResource']);
var transactionServices = angular.module('transactionServices', ['ngResource']);


couponServices.factory('Coupon', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_coupon_url + '/:coupon', {'coupon':'@code'},
            {query: {method:'GET'},
             create: {method:'POST'},
             update: {method:'PUT', isArray:false}});
  }]);

contributorServices.factory('Contributor', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_contributor_url + '/:user', {'user':'@user'});
  }]);

managerServices.factory('Manager', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_manager_url + '/:user', {'user':'@user'});
  }]);

subscriptionServices.factory('Subscription', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_subscription_url + '/:plan', {plan:'@plan'},
            {query: {method:'GET'}});
  }]);

transactionServices.factory('Transaction', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_transaction_url + '/:id', {id:'@id'},
            {query: {method:'GET'}});
  }]);

/*=============================================================================
  Controllers
  ============================================================================*/

var couponControllers = angular.module('couponControllers', []);
var contributorControllers = angular.module('contributorControllers', []);
var managerControllers = angular.module('managerControllers', []);
var subscriptionControllers = angular.module('subscriptionControllers', []);
var subscriberControllers = angular.module('subscriberControllers', []);
var transactionControllers = angular.module('transactionControllers', []);

couponControllers.controller('CouponListCtrl',
    ['$scope', '$http', '$timeout', 'Coupon', 'urls',
     function($scope, $http, $timeout, Coupon, urls) {
    $scope.urls = urls;
    $scope.totalItems = 0;
    $scope.dir = {code: 'asc'};
    $scope.params = {o: 'code', ot: $scope.dir['code']};
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
    $scope.numPages = 5;      // Total number of pages to display
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
            $scope.params['q'] = regex;
        } else {
            delete $scope.params['q'];
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
            $scope.params['page'] = $scope.currentPage;
        } else {
            delete $scope.params['page'];
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
        $scope.params['o'] = fieldName;
        $scope.params['ot'] = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params['page'];
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count != $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    }

    $scope.$watch('coupons', function(newVal, oldVal, scope) {
        if( newVal.hasOwnProperty('results')
            && oldVal.hasOwnProperty('results') ) {
            var length = ( oldVal.results.length < newVal.results.length ) ?
                oldVal.results.length : newVal.results.length;
            for( var i = 0; i < length; ++i ) {
                if( oldVal.results[i].ends_at != newVal.results[i].ends_at ) {
                    Coupon.update(newVal.results[i], function(result) {
                        // XXX message expiration date was updated.
                    });
                }
            }
        }
    }, true);

    $scope.editDescription = function (idx){
        $scope.edit_description = Array.apply(
            null, Array($scope.coupons.results.length)).map(function() {
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


contributorControllers.controller('contributorListCtrl',
    ['$scope', '$http', 'Contributor', 'urls',
    function($scope, $http, Contributor, urls) {

    $scope.users = Contributor.query();

    $scope.user = null;

    $scope.remove = function (idx) {
        Contributor.remove({ user: $scope.users[idx].username },
        function (success) {
            $scope.users.splice(idx, 1);
        });
    };

    $scope.save = function() {
        (new Contributor($scope.user)).$save(
            function(success) {
                /* XXX Couldn't figure out how to get the status code
                   here so we just reload the list. */
                $scope.users = Contributor.query();
            },
            function(error) {});
    };

    $scope.getUsers = function(val) {
        return $http.get(urls.saas_api_user_url, {
            params: {q: val}
        }).then(function(res){
            return res.data;
        });
    };

}]);


managerControllers.controller('managerListCtrl',
    ['$scope', '$http', 'Manager', 'urls',
    function($scope, $http, Manager, urls) {

    $scope.users = Manager.query();

    $scope.user = null;

    $scope.remove = function (idx) {
        Manager.remove({ user: $scope.users[idx].username },
        function (success) {
            $scope.users.splice(idx, 1);
        });
    };

    $scope.save = function() {
        (new Manager($scope.user)).$save(
            function(success) {
                /* XXX Couldn't figure out how to get the status code
                   here so we just reload the list. */
                $scope.users = Manager.query();
            },
            function(error) {});
    };

    $scope.getUsers = function(val) {
        return $http.get(urls.saas_api_user_url, {
            params: {q: val}
        }).then(function(res){
            return res.data;
        });
    };

}]);


subscriptionControllers.controller('subscriptionListCtrl',
    ['$scope', '$http', '$timeout', 'Subscription', 'urls',
    function($scope, $http, $timeout, Subscription, urls) {

    var defaultSortByField = 'organization';
    $scope.dir = {}
    $scope.totalItems = 0;
    $scope.dir[defaultSortByField] = 'asc';
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
    $scope.numPages = 5;      // Total number of pages to display
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
        entry['editDescription'] = true;
        $timeout(function() {
            input.focus();
        }, 100);
    };

    $scope.saveDescription = function(event, entry){
        if (event.which === 13 || event.type == 'blur' ){
            delete entry['editDescription'];
            $http.patch(urls.saas_api + entry.organization.slug
                + "/subscriptions/" + entry.plan.slug,
                {description: entry.description}).then(
                function(data){
                    // XXX message expiration date was updated.
            });
        }
    };

    $scope.filterList = function(regex) {
        if( regex ) {
            $scope.params['q'] = regex;
        } else {
            delete $scope.params['q'];
        }
        $scope.subscriptions = Subscription.query($scope.params, function() {
            if( $scope.subscriptions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.subscriptions.count;
            }
        });
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params['page'] = $scope.currentPage;
        } else {
            delete $scope.params['page'];
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
        $scope.params['o'] = fieldName;
        $scope.params['ot'] = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params['page'];
        $scope.subscriptions = Subscription.query($scope.params, function () {
            if( $scope.subscriptions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.subscriptions.count;
            }
        });
    }

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
    }
}]);


subscriberControllers.controller('subscriberCtrl',
    ['$scope', '$http', 'urls',
    function($scope, $http, urls) {

    $scope.opened = { 'start_at': false, 'ends_at': false }
    $scope.start_at = new Date();
    $scope.ends_at = new Date();

    $scope.minDate = new Date('2014-01-01');
    $scope.maxDate = new Date('2016-01-01');
    $scope.dateOptions = {formatYear: 'yy', startingDay: 1};
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    // initialized with *maxSize* empty items for layout during first load.
    $scope.registered = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    $scope.subscribed = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    $scope.churned = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];

    $scope.maxSize = 10;  // Limit number for pagination size
    $scope.numPages = 5;  // Total number of pages to display
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
        if( typeof dataset === "undefined" || dataset == 'churned' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.churned > 1 ) {
                params['offset'] = ($scope.currentPage.churned - 1)
                    * $scope.maxSize;
            }
            $http.get(urls.saas_api_churned, {
                params: params
            }).success(function(data) {
                $scope.churned = data;
                for( var i = $scope.churned.churned.length;
                     i < $scope.maxSize; ++i ) {
                    $scope.churned.churned.push({});
                }
            });
        }
        if( typeof dataset === "undefined" || dataset == 'registered' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.registered > 1 ) {
                params['offset'] = ($scope.currentPage.registered - 1)
                    * $scope.maxSize;
            }
            $http.get(urls.saas_api_registered, {
                params: params
            }).success(function(data) {
                $scope.registered = data;
                for( var i = $scope.registered.registered.length;
                     i < $scope.maxSize; ++i ) {
                    $scope.registered.registered.push({});
                }
            });
        }
        if( typeof dataset === "undefined" || dataset == 'subscribed' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.subscribed > 1 ) {
                params['offset'] = ($scope.currentPage.subscribed - 1)
                    * $scope.maxSize;
            }
            $http.get(urls.saas_api_subscribed, {
                params: params
            }).success(function(data) {
                $scope.subscribed = data;
                for( var i = $scope.subscribed.subscribed.length;
                     i < $scope.maxSize; ++i ) {
                    $scope.subscribed.subscribed.push({});
                }
            });
        }
    }

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
    }
}]);


transactionControllers.controller('transactionListCtrl',
    ['$scope', '$http', '$timeout', 'Transaction',
     function($scope, $http, $timeout, Transaction) {
    var defaultSortByField = 'date';
    $scope.dir = {};
    $scope.totalItems = 0;
    $scope.dir[defaultSortByField] = 'desc';
    $scope.params = {o: defaultSortByField, ot: $scope.dir[defaultSortByField]};
    $scope.transactions = Transaction.query($scope.params, function() {
        /* We cannot watch transactions.count otherwise things start
           to snowball. We must update totalItems only when it truly changed.*/
        if( $scope.transactions.count != $scope.totalItems ) {
            $scope.totalItems = $scope.transactions.count;
        }
    });

    $scope.filterExpr = '';
    $scope.itemsPerPage = 25; // Must match on the server-side.
    $scope.numPages = 5;      // Total number of pages to display
    $scope.currentPage = 1;
    /* currentPage will be saturated at maxSize when maxSize is defined. */

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
            $scope.params['q'] = regex;
        } else {
            delete $scope.params['q'];
        }
        $scope.transactions = Transaction.query($scope.params, function() {
            if( $scope.transactions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.transactions.count;
            }
        });
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params['page'] = $scope.currentPage;
        } else {
            delete $scope.params['page'];
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
        $scope.params['o'] = fieldName;
        $scope.params['ot'] = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params['page'];
        $scope.transactions = Transaction.query($scope.params, function() {
            if( $scope.transactions.count != $scope.totalItems ) {
                $scope.totalItems = $scope.transactions.count;
            }
        });
    }

}]);

