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


/*=============================================================================
  Services
  ============================================================================*/

var couponServices = angular.module('couponServices', ['ngResource']);
var contributorServices = angular.module('contributorServices', ['ngResource']);
var managerServices = angular.module('managerServices', ['ngResource']);
var subscriptionServices = angular.module('subscriptionServices', [
    'ngResource']);

couponServices.factory('Coupon', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_coupon_url + '/:coupon', {'coupon':'@code'},
            {create: {method:'POST'},
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
        urls.saas_api_subscription_url + '/:plan', {plan:'@plan'});
  }]);


/*=============================================================================
  Controllers
  ============================================================================*/

var couponControllers = angular.module('couponControllers', []);
var contributorControllers = angular.module('contributorControllers', []);
var managerControllers = angular.module('managerControllers', []);
var subscriptionControllers = angular.module('subscriptionControllers', []);

couponControllers.controller('CouponListCtrl',
    ['$scope', '$http', '$timeout', 'Coupon', 'urls',
     function($scope, $http, $timeout, Coupon, urls) {
    $scope.urls = urls;
    $scope.coupons = Coupon.query();

    $scope.newCoupon = new Coupon();

    $scope.remove = function (idx) {
        Coupon.remove({ coupon: $scope.coupons[idx].code }, function (success) {
            $scope.coupons.splice(idx, 1);
        });
    };

    $scope.save = function() {
        $http.post(urls.saas_api_coupon_url,$scope.newCoupon).success(
        function(result) {
            $scope.coupons.push(new Coupon(result));
            // Reset our editor to a new blank post
            $scope.newCoupon = new Coupon();
        });
    };

    // calendar for expiration date
    $scope.open = function($event, coupon) {
        $event.preventDefault();
        $event.stopPropagation();
        coupon.opened = true;
    };

    $scope.$watch('coupons', function(newVal, oldVal, scope) {
        var length = ( oldVal.length < newVal.length ) ?
            oldVal.length : newVal.length;
        for( var i = 0; i < length; ++i ) {
            if( oldVal[i].ends_at != newVal[i].ends_at ) {
                newVal[i].$update().then(function(result) {
                    // XXX message expiration date was updated.
                });
            }
        }
    }, true);

    $scope.dateOptions = {
        formatYear: 'yy',
        startingDay: 1
    };

    $scope.editDescription = function (idx){
        $scope.edit_description = Array.apply(null, Array($scope.coupons.length)).map(function() {
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
            coupon.$update();
        }
    };

    $scope.initDate = new Date('2016-15-20');
    $scope.minDate = new Date();
    $scope.maxDate = new Date('2016-01-01');
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];
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
    ['$scope', '$http', 'Subscription', 'urls',
    function($scope, $http, Subscription, urls) {

    $scope.unsubscribe = function(url) {
        if( confirm("Are you sure?") ) {
            $http.$delete(url).then(function(data){ location.reload(); });
        }
    }
}]);

